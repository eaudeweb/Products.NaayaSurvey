# The contents of this file are subject to the Mozilla Public
# License Version 1.1 (the "License"); you may not use this file
# except in compliance with the License. You may obtain a copy of
# the License at http://www.mozilla.org/MPL/
#
# Software distributed under the License is distributed on an "AS
# IS" basis, WITHOUT WARRANTY OF ANY KIND, either express or
# implied. See the License for the specific language governing
# rights and limitations under the License.
#
# The Initial Owner of the Original Code is European Environment
# Agency (EEA).  Portions created by Finsiel Romania and Eau de Web are
# Copyright (C) European Environment Agency.  All
# Rights Reserved.
#
# Authors:
#
# Alin Voinea, Eau de Web

# Zope imports
from DateTime import DateTime
from OFS.Folder import Folder
from OFS.Traversable import path2url
from AccessControl import ClassSecurityInfo
from Globals import InitializeClass
from ZPublisher.HTTPRequest import FileUpload
from zLOG import LOG, INFO
from zope import interface

# Products import
from Products.ExtFile.ExtFile import manage_addExtFile
from Products.NaayaCore.managers.utils import utils
from Products.NaayaBase.constants import EXCEPTION_NOTAUTHORIZED
from Products.NaayaBase.constants import EXCEPTION_NOTAUTHORIZED_MSG
from Products.NaayaCore.FormsTool.NaayaTemplate import NaayaPageTemplateFile

from permissions import PERMISSION_VIEW_ANSWERS
from interfaces import INySurveyAnswer

gUtil = utils()

def manage_addSurveyAnswer(context, datamodel, respondent=None, REQUEST=None):
    """ Constructor for SurveyAnswer"""
    global gUtil

    if respondent is None and REQUEST is not None:
            respondent = REQUEST.AUTHENTICATED_USER.getUserName()

    # calculate an available id
    while True:
        idSuffix = gUtil.utGenRandomId()
        id = datamodel['id'] = 'answer_%s' % (idSuffix, )
        if id not in context.objectIds():
            break

    ob = SurveyAnswer(id, datamodel, respondent)
    context._setObject(id, ob)
    ob = context._getOb(id)

    # handle files
    for key, value in datamodel.items():
        if isinstance(value, FileUpload):
            ob.handle_upload(key, value)


    return id


class SurveyAnswer(Folder):
    """ Class used to store survey answers"""

    interface.implements(INySurveyAnswer)

    meta_type = "Naaya Survey Answer"
    meta_label = "Survey Answer"
    icon = 'misc_/NaayaSurvey/NySurveyAnswer.gif'

    _constructors = (manage_addSurveyAnswer,)
    _properties=()
    all_meta_types = ()
    manage_options=(
        {'label':'Properties', 'action':'manage_propertiesForm',
         'help':('OFSP','Properties.stx')},
        {'label':'View', 'action':'index_html'},
        {'label':'Contents', 'action':'manage_main',
         'help':('OFSP','ObjectManager_Contents.stx')},
     )

    security = ClassSecurityInfo()

    def __init__(self, id, datamodel, respondent):
        Folder.__init__(self, id)
        self.add_properties(datamodel)
        self.respondent = respondent
        self.modification_time = DateTime()

    security.declarePrivate('add_properties')
    def add_properties(self, datamodel):
        for key, value in datamodel.items():
            self.edit_property(key, value)

    def edit_property(self, key, value):
        if isinstance(value, FileUpload):
            return # Handle somewhere else
        setattr(self, key, value)

    security.declarePrivate('handle_upload')
    def handle_upload(self, id, attached_file):
        if id in self.objectIds():
            self.manage_delObjects([id,])
        manage_addExtFile(self, id, title=attached_file.filename,
                          file=attached_file)

    security.declareProtected(PERMISSION_VIEW_ANSWERS, 'getDatamodel')
    def getDatamodel(self):
        """ """
        return dict([(widget.id, self.get(widget.id))
                     for widget in self.getSurveyTemplate().getSortedWidgets()])

    def get(self, widget_id, default=None):
        """Returns the value for widget_id, else default"""
        return getattr(self.aq_explicit, widget_id, default)

    # The special permission PERMISSION_VIEW_ANSWERS is used instead of the
    # regular "view" permission because otherwise, by default, all users
    # (including anonymous ones) can see all answers. Also setting the view
    # permission for each SurveyAnswer wouldn't be practical.

    _index_html = NaayaPageTemplateFile('zpt/surveyanswer_index',
                    globals(), 'NaayaSurvey.surveyanswer_index')
    def index_html(self,REQUEST=None):
        """ Return the answer index if the current user
        is the respondent or has permission to view answers """

        if REQUEST:
            if self.respondent == REQUEST.AUTHENTICATED_USER.getUserName():
                return self._index_html()

        if self.checkPermission(PERMISSION_VIEW_ANSWERS):
            return self._index_html()
        else:
            raise EXCEPTION_NOTAUTHORIZED, EXCEPTION_NOTAUTHORIZED_MSG

    def index_csv(self, REQUEST=None, **kwargs):
        """ Return values formated as csv.
        """
        datamodel=self.getDatamodel()
        widgets = self.getSortedWidgets()
        atool = self.getSite().getAuthenticationTool()
        respondent = atool.getUserFullNameByID(self.respondent)
        res = ['"%s"' % respondent]
        for widget in widgets:
            res.append(widget.render_csv(
                datamodel=datamodel.get(widget.id, None), **kwargs))
        return ','.join(res)

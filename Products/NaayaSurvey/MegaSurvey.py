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
# Cristian Ciupitu, Eau de Web

# Zope imports
from AccessControl import ClassSecurityInfo
from AccessControl.Permissions import view
from DateTime import DateTime
from Globals import InitializeClass
from zLOG import LOG, ERROR, DEBUG
from AccessControl.Permissions import change_permissions

# Product imports
from Products.NaayaBase.constants import PERMISSION_EDIT_OBJECTS
from Products.NaayaCore.managers.utils import genRandomId, tmpfile, make_id
from Products.NaayaBase.NyAccess import NyAccess
from Products.NaayaCore.FormsTool.NaayaTemplate import NaayaPageTemplateFile

from BaseSurveyTemplate import BaseSurveyTemplate
from SurveyQuestionnaire import SurveyQuestionnaire
from permissions import (PERMISSION_ADD_MEGASURVEY, PERMISSION_ADD_ANSWER,
                         PERMISSION_ADD_REPORT, PERMISSION_ADD_ATTACHMENT,
                         PERMISSION_VIEW_ANSWERS, PERMISSION_EDIT_ANSWERS,
                         PERMISSION_VIEW_REPORTS)

def manage_addMegaSurvey(context, id='', title='', lang=None, REQUEST=None, **kwargs):
    """ """
    if not title:
        title = 'Survey'
    id = make_id(context, id=id, title=title)

    # Get selected language
    lang = REQUEST and REQUEST.form.get('lang', None)
    lang = lang or kwargs.get('lang', context.gl_get_selected_language())

    if REQUEST:
        kwargs.update(REQUEST.form)
    kwargs['releasedate'] = context.process_releasedate(kwargs.get('releasedate', DateTime()))
    kwargs['expirationdate'] = context.process_releasedate(kwargs.get('expirationdate', DateTime()))
    contributor = context.REQUEST.AUTHENTICATED_USER.getUserName()
    #log post date
    auth_tool = context.getAuthenticationTool()
    auth_tool.changeLastPost(contributor)

    kwargs.setdefault('id', id)
    kwargs.setdefault('title', title)
    kwargs.setdefault('lang', lang)

    ob = MegaSurvey(**kwargs)
    context.gl_add_languages(ob)
    context._setObject(id, ob)

    ob = context._getOb(id)
    ob.updatePropertiesFromGlossary(lang)
    ob.submitThis()
    context.recatalogNyObject(ob)

    # Return
    if not REQUEST:
        return id
    #redirect if case
    if REQUEST.has_key('submitted'): ob.submitThis()
    l_referer = REQUEST['HTTP_REFERER'].split('/')[-1]
    if l_referer == 'megasurvey_manage_add' or l_referer.find('megasurvey_manage_add') != -1:
        return context.manage_main(context, REQUEST, update_menu=1)
    elif l_referer == 'megasurvey_add_html':
        context.setSession('referer', context.absolute_url())
        REQUEST.RESPONSE.redirect('%s/messages_html' % context.absolute_url())

class MegaSurvey(SurveyQuestionnaire, BaseSurveyTemplate):
    """ """

    meta_type = 'Naaya Mega Survey'
    meta_label = 'Survey'

    _constructors = (manage_addMegaSurvey, )

    security = ClassSecurityInfo()

    edit_access = NyAccess('edit_access', {
        PERMISSION_ADD_ANSWER: "Submit answer",
        PERMISSION_ADD_REPORT: "Create report",
        PERMISSION_ADD_ATTACHMENT: "Attach file",
        PERMISSION_VIEW_ANSWERS: "View answers",
        PERMISSION_EDIT_ANSWERS: "Edit answers",
        PERMISSION_VIEW_REPORTS: "View reports",
    })

    def __init__(self, id, **kwargs):
        """ """
        #BaseSurveyTemplate.__init__(self, id, **kwargs)
        SurveyQuestionnaire.__init__(self, id, None, **kwargs)
        self.approved = 1

    def all_meta_types(self, interfaces=None):
        """What can you put inside me?"""
        return BaseSurveyTemplate.all_meta_types(self, interfaces)

    security.declareProtected(view, 'getSurveyTemplate')
    def getSurveyTemplate(self):
        """Return the survey template used for this questionnaire"""
        return self

    security.declareProtected(view, 'getSurveyTemplateId')
    def getSurveyTemplateId(self):
        """Return survey template id; used by the catalog tool."""
        return None

    security.declareProtected(view, 'download')
    def download(self, REQUEST=None, RESPONSE=None):
        """returns all the answers in a csv file"""
        RESPONSE.setHeader('Content-Type', 'text/csv')
        RESPONSE.setHeader('Content-Disposition', 'attachment; filename=%s.csv' % self.id)
        answers = self.getAnswers()
        widgets = self.getSortedWidgets()
        res = '"Respondent",'
        res += ','.join(['"%s"' % widget.title_or_id() for widget in widgets])
        res = [res,]
        res.extend([answer.index_csv() for answer in answers])
        return '\n'.join(res)
    #
    # Site pages
    #
    security.declareProtected(PERMISSION_ADD_MEGASURVEY, 'megasurvey_add_html')
    megasurvey_add_html = NaayaPageTemplateFile('zpt/megasurvey_add',
                          globals(), 'NaayaSurvey.megasurvey_add')

    security.declareProtected(view, 'index_html')
    index_html = NaayaPageTemplateFile('zpt/megasurvey_index',
                     globals(), 'NaayaSurvey.megasurvey_index')

    security.declareProtected(PERMISSION_EDIT_OBJECTS, 'edit_html')
    edit_html = NaayaPageTemplateFile('zpt/megasurvey_edit',
                    globals(), 'NaayaSurvey.megasurvey_edit')

    security.declareProtected(PERMISSION_EDIT_OBJECTS, 'edit_attachments_html')
    edit_attachments_html = NaayaPageTemplateFile('zpt/megasurvey_edit_attachments',
                        globals(), 'NaayaSurvey.megasurvey_edit_attachments')

    security.declareProtected(PERMISSION_EDIT_OBJECTS, 'edit_questions_html')
    edit_questions_html = NaayaPageTemplateFile('zpt/megasurvey_edit_questions',
                        globals(), 'NaayaSurvey.megasurvey_edit_questions')

    security.declareProtected(PERMISSION_EDIT_OBJECTS, 'edit_reports_html')
    edit_reports_html = NaayaPageTemplateFile('zpt/megasurvey_edit_reports',
                        globals(), 'NaayaSurvey.megasurvey_edit_reports')

    #
    # change the security of the inherited methods
    #
    security.declareProtected(PERMISSION_EDIT_OBJECTS, 'saveProperties')
    security.declareProtected(PERMISSION_EDIT_OBJECTS, 'addWidget')
    security.declareProtected(PERMISSION_EDIT_OBJECTS, 'deleteItems')
    security.declareProtected(PERMISSION_EDIT_OBJECTS, 'setSortOrder')
    security.declareProtected(PERMISSION_EDIT_OBJECTS, 'addReport')
    security.declareProtected(PERMISSION_EDIT_OBJECTS, 'generateFullReport')
    security.declareProtected(PERMISSION_EDIT_OBJECTS, 'addAttachment')

InitializeClass(MegaSurvey)

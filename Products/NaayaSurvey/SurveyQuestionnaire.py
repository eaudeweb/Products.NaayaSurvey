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

# Python imports
import sys
from urllib import urlencode
from os import path

# Zope imports
from Acquisition import Implicit
from AccessControl import ClassSecurityInfo
from AccessControl.Permissions import view, view_management_screens
from DateTime import DateTime
from Globals import InitializeClass
from OFS.Traversable import path2url
from ZPublisher import BadRequest, InternalError, NotFound
from ZPublisher.HTTPRequest import FileUpload
from zLOG import LOG, ERROR, DEBUG
from Products.PageTemplates.PageTemplateFile import PageTemplateFile
from Products.PageTemplates.ZopePageTemplate import manage_addPageTemplate
from Products.PythonScripts.PythonScript import manage_addPythonScript

# Product imports
from Products.Naaya.constants import DEFAULT_SORTORDER
from Products.NaayaBase.NyContainer import NyContainer
from Products.NaayaBase.NyAttributes import NyAttributes
from Products.NaayaBase.NyImageContainer import NyImageContainer
from Products.NaayaBase.NyCheckControl import NyCheckControl
from Products.NaayaBase.constants import \
     EXCEPTION_NOTAUTHORIZED, EXCEPTION_NOTAUTHORIZED_MSG, \
     MESSAGE_SAVEDCHANGES, PERMISSION_EDIT_OBJECTS, \
     PERMISSION_SKIP_CAPTCHA
from Products.NaayaCore.managers.utils import genObjectId, genRandomId
from Products.NaayaCore.managers import recaptcha_utils
from Products.NaayaCore.FormsTool.NaayaTemplate import NaayaPageTemplateFile
from Products.NaayaWidgets.Widget import WidgetError
from Products.NaayaBase.NyRoleManager import NyRoleManager
from naaya.core.zope2util import folder_manage_main_plus

from SurveyAnswer import manage_addSurveyAnswer, SurveyAnswer
from SurveyReport import manage_addSurveyReport
from permissions import *
from questionnaire_item import questionnaire_item

from migrations import available_migrations, perform_migration

class SurveyQuestionnaireException(Exception):
    """Survey related exception"""
    pass

def manage_addSurveyQuestionnaire(context, id='', title='', lang=None, REQUEST=None, **kwargs):
    """ """
    if not title:
        title = 'Survey Instance'
    if not id:
        id = genObjectId(title)

    idSuffix = ''
    while id+idSuffix in context.objectIds():
        idSuffix = genRandomId(p_length=4)
    id = id + idSuffix

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

    kwargs['id'] = id
    kwargs.setdefault('title', title)
    kwargs.setdefault('lang', lang)

    ob = SurveyQuestionnaire(**kwargs)
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
    if l_referer == 'questionnaire_manage_add' or l_referer.find('questionnaire_manage_add') != -1:
        return context.manage_main(context, REQUEST, update_menu=1)
    elif l_referer == 'questionnaire_add_html':
        context.setSession('referer', context.absolute_url())
        REQUEST.RESPONSE.redirect('%s/messages_html' % context.absolute_url())

class SurveyQuestionnaire(NyRoleManager, NyAttributes, questionnaire_item, NyContainer):
    """ """
    meta_type = "Naaya Survey Questionnaire"
    meta_label = "Survey Instance"
    icon = 'misc_/NaayaSurvey/NySurveyQuestionnaire.gif'
    icon_marked = 'misc_/NaayaSurvey/NySurveyQuestionnaire_marked.gif'

    _constructors = (manage_addSurveyQuestionnaire,)

    all_meta_types = ()

    manage_options=(
        {'label':'Contents', 'action':'manage_main',
          'help':('OFSP','ObjectManager_Contents.stx')},
        {'label':'Properties', 'action':'manage_propertiesForm',
         'help':('OFSP','Properties.stx')},
        {'label':'View', 'action':'index_html'},
        {'label':'Migrations', 'action':'manage_migrate_html'},
        {'label':'Security', 'action':'manage_access',
         'help':('OFSP', 'Security.stx')},
      )

    security = ClassSecurityInfo()

    notify_owner = True
    notify_respondents = 'LET_THEM_CHOOSE_YES'
    allow_overtime = 0

    def __init__(self, id, survey_template, lang=None, **kwargs):
        """
            @param id: id
            @param survey_template: id of the survey template
        """
        self.id = id
        self._survey_template = survey_template

        self.save_properties(lang=lang, **kwargs)
        NyContainer.__dict__['__init__'](self)
        self.imageContainer = NyImageContainer(self, True)

    #
    # Self edit methods
    #
    security.declareProtected(PERMISSION_EDIT_OBJECTS, 'saveProperties')
    def saveProperties(self, REQUEST=None, **kwargs):
        """ """
        if REQUEST:
            kwargs.update(REQUEST.form)
        lang = kwargs.get('lang', self.get_selected_language())

        kwargs.setdefault('title', '')
        kwargs.setdefault('description', '')
        kwargs.setdefault('keywords', '')
        kwargs.setdefault('coverage', '')
        kwargs.setdefault('sortorder', DEFAULT_SORTORDER)

        releasedate = kwargs.get('releasedate', DateTime())
        releasedate = self.process_releasedate(releasedate)
        kwargs['releasedate'] = releasedate

        expirationdate = kwargs.get('expirationdate', DateTime())
        expirationdate = self.process_releasedate(expirationdate)
        kwargs['expirationdate'] = expirationdate

        self.save_properties(**kwargs)
        self.updatePropertiesFromGlossary(lang)
        self.recatalogNyObject(self)

        if REQUEST:
            # Log date
            contributor = REQUEST.AUTHENTICATED_USER.getUserName()
            auth_tool = self.getAuthenticationTool()
            auth_tool.changeLastPost(contributor)
            # Redirect
            self.setSessionInfoTrans(MESSAGE_SAVEDCHANGES, date=self.utGetTodayDate())
            REQUEST.RESPONSE.redirect('%s/edit_html?lang=%s' % (self.absolute_url(), lang))

    #
    # Methods required by the Naaya framework
    #
    security.declareProtected(view, 'hasVersion')
    def hasVersion(self):
        """ """
        return False

    security.declareProtected(view, 'getVersionLocalProperty')
    def getVersionLocalProperty(self, id, lang):
        """ """
        return self.getLocalProperty(id, lang)

    security.declareProtected(view, 'getVersionProperty')
    def getVersionProperty(self, id):
        """ """
        return getattr(self, id, '')

    security.declareProtected(view, 'getSurveyTemplate')
    def getSurveyTemplate(self):
        """Return the survey template used for this questionnaire"""
        stool = self.portal_survey
        return getattr(stool, self._survey_template)

    security.declareProtected(view, 'getSurveyTemplateId')
    def getSurveyTemplateId(self):
        """Return survey template id; used by the catalog tool."""
        stype = self.getSurveyTemplate()
        if not stype:
            return ''
        return stype.getId()

    #
    # Answer edit methods
    #
    security.declareProtected(PERMISSION_ADD_ANSWER, 'addSurveyAnswer')
    def addSurveyAnswer(self, REQUEST=None, notify_respondent=False, **kwargs):
        """Add someone's answer"""
        try:
            if self.expired():
                raise SurveyQuestionnaireException("The survey has expired")
        except SurveyQuestionnaireException, ex:
            if REQUEST:
                self.setSessionErrorsTrans(str(ex))
                return REQUEST.RESPONSE.redirect('%s/index_html' % self.absolute_url())
            else:
                raise

        datamodel = {}
        errors = []
        for widget in self.getSurveyTemplate().getWidgets():
            try:
                value = widget.getDatamodel(REQUEST.form)
                widget.validateDatamodel(value)
                datamodel[widget.getWidgetId()] = value
            except WidgetError, ex:
                if not REQUEST:
                    raise
                datamodel[widget.getWidgetId()] = None
                errors.append(str(ex))

        #check Captcha/reCaptcha
        if not self.checkPermission(PERMISSION_SKIP_CAPTCHA):
            captcha_errors = self.getSite().validateCaptcha('', REQUEST)
            if captcha_errors:
                errors.append(captcha_errors)

        try:
            validation_onsubmit = self['validation_onsubmit']
        except KeyError:
            pass
        else:
            validation_onsubmit(datamodel, errors)

        if errors:
            self.setSessionErrorsTrans(errors)
            self.setSessionAnswer(datamodel)
            self.setSession('notify_respondent', notify_respondent)
            REQUEST.RESPONSE.redirect('%s/index_html' % self.absolute_url())
            return

        old_answer = self.getMyAnswer()
        if old_answer is not None:
            self._delObject(old_answer.id)
            LOG('NaayaSurvey.SurveyQuestionnaire', DEBUG, 'Deleted previous answer %s' % (old_answer.absolute_url()))

        answer_id = manage_addSurveyAnswer(self, datamodel, REQUEST=REQUEST)
        answer = self._getOb(answer_id)
        if self.notify_owner:
            self.sendNotificationToOwner(answer)
        if self.notify_respondents == 'ALWAYS' or \
           self.notify_respondents.startswith('LET_THEM_CHOOSE') and notify_respondent:
            self.sendNotificationToRespondent(answer)
        self.delSessionKeys(datamodel.keys())

        if REQUEST:
            self.setSession('title', 'Thank you for taking the survey')
            self.setSession('body', '')
            self.setSession('referer', self.aq_parent.absolute_url())
            REQUEST.RESPONSE.redirect('%s/messages_html' % self.absolute_url())
        return answer_id

    #
    # Email notifications
    #

    security.declarePrivate('sendNotificationToOwner')
    def sendNotificationToOwner(self, answer):
        """Send an email notifications about the newly added answer to the owner of the survey.

            @param answer: the answer object that was added
            @type answer: SurveyAnswer
        """
        owner = self.getOwner()
        respondent = self.REQUEST.AUTHENTICATED_USER
        auth_tool = self.getSite().getAuthenticationTool()

        d = {}
        d['NAME'] = auth_tool.getUserFullName(owner)
        d['RESPONDENT'] = "User %s" % auth_tool.getUserFullName(respondent)
        d['SURVEY_TITLE'] = self.title
        d['SURVEY_URL'] = self.absolute_url()
        d['LINK'] = answer.absolute_url()

        self._sendEmailNotification('email_survey_answer', d, owner)

    security.declarePrivate('sendNotificationToRespondent')
    def sendNotificationToRespondent(self, answer):
        """Send an email notification about the newly added answer to the respondent.
            If the respondent is an anonymous user no notification will be sent.

            @param answer: the answer object that was added (unsed for the moment)
            @type answer: SurveyAnswer
        """
        if self.isAnonymousUser():
            return

        owner = self.getOwner()
        respondent = self.REQUEST.AUTHENTICATED_USER
        auth_tool = self.getSite().getAuthenticationTool()

        d = {}
        d['NAME'] = auth_tool.getUserFullName(respondent)
        d['SURVEY_TITLE'] = self.title
        d['SURVEY_URL'] = self.absolute_url()
        d['LINK'] = "%s" % answer.absolute_url()

        self._sendEmailNotification('email_survey_answer_to_respondent', d, respondent)

    security.declarePrivate('_sendEmailNotification')
    def _sendEmailNotification(self, template_name, d, recipient):
        """Send an email notification.

            @param template_name: name of the email template
            @type template_name: string
            @param d: dictionary with the values used in the template
            @type d: dict
            @param recipient: recipient
            @type recipient: Zope User
        """
        auth_tool = self.getSite().getAuthenticationTool()
        email_tool = self.getSite().getEmailTool()
        template = email_tool._getOb(template_name)

        try:
            sender_email = self.getNotificationTool().from_email
        except AttributeError:
            sender_email = email_tool._get_from_address()

        try:
            recp_email = auth_tool.getUserEmail(recipient)
            email_tool.sendEmail(template.body % d,
                                 recp_email,
                                 sender_email,
                                 template.title)
            LOG('NaayaSurvey.SurveyQuestionnaire', DEBUG, 'Notification sent from %s to %s' % (sender_email, recp_email))
        except:
            # possible causes - the recipient doesn't have email (e.g. regular Zope user)
            #                 - we can not send the email
            # these aren't fatal errors, so we'll just log the error
            err = sys.exc_info()
            LOG('NaayaSurvey.SurveyQuestionnaire', ERROR, 'Could not send email notification for survey %s' % (self.absolute_url(),), error=err)

    #
    # Answer read methods
    #
    security.declareProtected(PERMISSION_VIEW_ANSWERS, 'getAnswers')
    def getAnswers(self):
        """Return a list of answers"""
        return self.objectValues(SurveyAnswer.meta_type)

    # this is method is used by the widget manage forms
    security.declareProtected(PERMISSION_EDIT_OBJECTS, 'getAnswerCountForQuestion')
    def getAnswerCountForQuestion(self, question_id, exclude_None=False):
        """Return the count of answers for question_id, excluding None ones if exclude_None if True."""
        L = [answer.get(question_id) for answer in self.getAnswers()]
        if exclude_None:
            L = [x for x in L if x is not None]
        return len(L)

    security.declarePublic('getMyAnswer')
    def getMyAnswer(self):
        """Return the answer of the current user or None if it doesn't exist.

            If multiple answers exist, only the first one is returned.
        """
        if self.isAnonymousUser():
            return None
        respondent = self.REQUEST.AUTHENTICATED_USER.getUserName()
        catalog = self.getCatalogTool()
        for brain in catalog({'path': path2url(self.getPhysicalPath()),
                              'meta_type': SurveyAnswer.meta_type,
                              'respondent': respondent}):
            obj = brain.getObject()
            # if the "respondent" index is missing for some reason, we get
            # all answers, so we must do the filtering ourselves.
            if obj.respondent != respondent:
                continue
            return obj
        return None

    security.declarePublic('getMyAnswerDatamodel')
    def getMyAnswerDatamodel(self):
        """ """
        answer = self.getMyAnswer()
        if answer is None:
            return {}
        return answer.getDatamodel()

    security.declarePrivate('setSessionAnswer')
    def setSessionAnswer(self, datamodel):
        """Sets the session with the specified answer"""
        for widget_id, value in datamodel.items():
            if value is None:
                continue
            if isinstance(value, FileUpload):
                continue
            self.setSession(widget_id, value)

    security.declareProtected(PERMISSION_VIEW_REPORTS, 'questionnaire_view_report_html')
    def questionnaire_view_report_html(self, report_id, REQUEST):
        """View the report report_id"""
        report = self.getSurveyTemplate().getReport(report_id)
        if not report:
            raise NotFound('Report %s' % (report_id,))
        return report.view_report_html(answers=self.getAnswers())

    #
    # utils
    #
    security.declareProtected(view, 'expired')
    def expired(self):
        """
        expired():
        -> true if the expiration date has been exceeded,
        -> false if the expiration date is still to be reached or
        if the survey allows posting after the expiration date.
        """


        if self.allow_overtime:
            return False
        now = DateTime()
        expire_date = DateTime(self.expirationdate) + 1
        return now.greaterThan(expire_date)

    security.declareProtected(view, 'get_days_left')
    def get_days_left(self):
        """ Returns the remaining days for the survey or the number of days before it starts """
        today = self.utGetTodayDate().earliestTime()
        if self.releasedate.lessThanEqualTo(today):
            return (1, int(str((self.expirationdate + 1) - today).split('.')[0]))
        else:
            return (0, int(str(self.releasedate - today).split('.')[0]))

    security.declarePublic('checkPermissionViewAnswers')
    def checkPermissionViewAnswers(self):
        """Check if the user has the VIEW_ANSWERS permission"""
        return self.checkPermission(PERMISSION_VIEW_ANSWERS) or self.checkPermissionPublishObjects()

    security.declarePublic('checkPermissionViewReports')
    def checkPermissionViewReports(self):
        """Check if the user has the VIEW_REPORTS permission"""
        return self.checkPermission(PERMISSION_VIEW_REPORTS)

    security.declarePublic('checkPermissionEditObjects')
    def checkPermissionEditObjects(self):
        """Check if the user has the EDIT_OBJECTS permission"""
        return self.checkPermission(PERMISSION_EDIT_OBJECTS)

    security.declarePublic('checkPermissionAddAnswer')
    def checkPermissionAddAnswer(self):
        """Check if the user has the ADD_ANSWER permission"""
        return self.checkPermission(PERMISSION_ADD_ANSWER)

    #
    # Site pages
    #
    security.declareProtected(PERMISSION_ADD_QUESTIONNAIRE, 'questionnaire_add_html')
    questionnaire_add_html = NaayaPageTemplateFile('zpt/questionnaire_add',
                             globals(), 'NaayaSurvey.questionnaire_add')

    security.declareProtected(view, 'index_html')
    index_html = NaayaPageTemplateFile('zpt/questionnaire_index',
                     globals(), 'NaayaSurvey.questionnaire_index')

    security.declareProtected(PERMISSION_EDIT_OBJECTS, 'edit_html')
    edit_html = NaayaPageTemplateFile('zpt/questionnaire_edit',
                    globals(), 'NaayaSurvey.questionnaire_edit')

    security.declareProtected(PERMISSION_VIEW_REPORTS, 'view_reports_html')
    view_reports_html = NaayaPageTemplateFile('zpt/questionnaire_view_reports',
                        globals(), 'NaayaSurvey.questionnaire_view_reports')

    security.declareProtected(PERMISSION_VIEW_ANSWERS, 'view_answers_html')
    view_answers_html = NaayaPageTemplateFile('zpt/questionnaire_view_answers',
                        globals(), 'NaayaSurvey.questionnaire_view_answers')

    manage_main = folder_manage_main_plus
    ny_before_listing = PageTemplateFile('zpt/questionnaire_manage_header',
                                         globals())

    security.declareProtected(view_management_screens,
                              'manage_create_validation_html')
    def manage_create_validation_html(self, REQUEST=None):
        """ create a blank validation_html template in this survey """
        datafile = path.join(path.dirname(__file__), 'www',
                             'initial_validation_html.txt')
        id = 'validation_html'
        title = "Custom questionnaire HTML"
        manage_addPageTemplate(self, id, title, open(datafile).read())
        if REQUEST is not None:
            url = self[id].absolute_url() + '/manage_workspace'
            REQUEST.RESPONSE.redirect(url)

    security.declareProtected(view_management_screens,
                              'manage_create_validation_onsubmit')
    def manage_create_validation_onsubmit(self, REQUEST=None):
        """ create a blank validation_onsubmit template in this survey """
        datafile = path.join(path.dirname(__file__), 'www',
                             'initial_validation_onsubmit.txt')
        id = 'validation_onsubmit'
        manage_addPythonScript(self, id)
        self._getOb(id).write(open(datafile, 'rb').read())
        if REQUEST is not None:
            url = self[id].absolute_url() + '/manage_workspace'
            REQUEST.RESPONSE.redirect(url)

    security.declarePublic('view_my_answer_html')
    def view_my_answer_html(self, REQUEST):
        """Display a page with the answer of the current user"""
        answer = self.getMyAnswer()
        if answer is None:
            raise NotFound("You haven't taken this survey") # TODO: replace with a proper exception/error message
        return answer.index_html(REQUEST=REQUEST)

    #
    # macros & other html snippets
    #
    security.declareProtected(view, 'base_index_html')
    base_index_html = NaayaPageTemplateFile('zpt/base_questionnaire_index',
                          globals(), 'NaayaSurvey.base_questionnaire_index')

    security.declareProtected(view, 'showCaptcha')
    def showCaptcha(self):
        """Return HTML code for CAPTCHA"""
        return recaptcha_utils.render_captcha(self)

    security.declareProtected(view_management_screens, 'manage_migrate')
    def manage_migrate(self, REQUEST, widget_id, convert_to):
        """ convert widget type """
        perform_migration(self, widget_id, convert_to)
        self.setSessionInfo(["Changed widget type for %r" % widget_id])
        REQUEST.RESPONSE.redirect(self.absolute_url() + '/manage_migrate_html')

    security.declareProtected(view_management_screens, 'manage_migrate_html')
    manage_migrate_html = PageTemplateFile('zpt/questionnaire_manage_migrate',
                                           globals())
    manage_migrate_html.available_migrations = available_migrations

InitializeClass(SurveyQuestionnaire)

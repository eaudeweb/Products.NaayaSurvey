# Pythons imports
from unittest import TestSuite, makeSuite

# Zope imports
from Testing import ZopeTestCase
from DateTime import DateTime

# Naaya imports
from Products.Naaya.tests.NaayaTestCase import NaayaTestCase
from Products.NaayaBase.NyRoleManager import NyRoleManager

# Survey imports
from Products.NaayaSurvey.MegaSurvey import manage_addMegaSurvey
from Products.NaayaSurvey.SurveyQuestionnaire import SurveyQuestionnaire, SurveyQuestionnaireException
from Products.NaayaSurvey.SurveyReport import SurveyReport
from Products.NaayaSurvey.SurveyTool import SurveyTool, manage_addSurveyTool
from Products.NaayaWidgets.widgets import AVAILABLE_WIDGETS

ZopeTestCase.installProduct('NaayaWidgets')
ZopeTestCase.installProduct('NaayaSurvey')

class MegaSurveyTestCase(NaayaTestCase):
    """Mega Survey test cases"""

    def afterSetUp(self):
        self.login()
        manage_addSurveyTool(self.portal)
        id = manage_addMegaSurvey(self.portal, title='Testing survey')
        self.survey = self.portal._getOb(id)

    def beforeTearDown(self):
        self.logout()

    def testAddQuestions(self):
        """Add questions"""
        for widget_class in AVAILABLE_WIDGETS:
            title = 'A question'
            id = self.survey.addWidget(title=title, meta_type=widget_class.meta_type)
            w = self.survey._getOb(id, None)
            self.assertNotEqual(w, None)
            self.assert_(isinstance(w, widget_class))
            self.assertEqual(w.getLocalAttribute('title', self.portal.gl_get_selected_language()), title)

    def testAddReport(self):
        """Add report"""
        title = 'A report'
        id = self.survey.addReport(title=title)
        report = self.survey._getOb(id, None)
        self.assertNotEqual(report, None)
        self.assert_(isinstance(report, SurveyReport))
        self.assertEqual(report.getLocalAttribute('title', self.portal.gl_get_selected_language()), title)

    def testGenerateFullReport(self):
        """Generate full report"""
        title = 'Full report'
        id = self.survey.generateFullReport(title=title)
        report = self.survey._getOb(id, None)
        self.assertNotEqual(report, None)
        self.assert_(isinstance(report, SurveyReport))
        self.assertEqual(report.getLocalAttribute('title', self.portal.gl_get_selected_language()), title)
        self.assertEqual(len(report.getStatistics()), 0) # 0 questions -> 0 statistics

    def testTakingSurvey(self):
        """Test taking a survey"""
        answer = self.survey.getMyAnswer()
        self.assertEqual(answer, None)

        self.survey.expirationdate = DateTime() + 5
        self.survey.addSurveyAnswer(notify_respondent=False)

        self.survey.expirationdate = DateTime() - 5
        self.assertRaises(SurveyQuestionnaireException, self.survey.addSurveyAnswer, notify_respondent=False)

    def test_NyRoleManager_wrappers(self):
        self.assertTrue(SurveyQuestionnaire.manage_addLocalRoles == NyRoleManager.manage_addLocalRoles)
        self.assertTrue(SurveyQuestionnaire.manage_setLocalRoles == NyRoleManager.manage_setLocalRoles)
        self.assertTrue(SurveyQuestionnaire.manage_delLocalRoles == NyRoleManager.manage_delLocalRoles)


def test_suite():
    suite = TestSuite()
    suite.addTest(makeSuite(MegaSurveyTestCase))
    return suite

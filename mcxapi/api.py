import logging
import requests

from collections import namedtuple
from anytree import RenderTree, NodeMixin

Inbox = namedtuple('Inbox', 'ids fieldnames cases')


class McxApi:
    base_url = "https://{}.allegiancetech.com/CaseManagement.svc/{}"

    def __init__(self, instance, company, user, password, headers=None):
        self.log = logging.getLogger('{0.__module__}.{0.__name__}'.format(self.__class__))
        self.instance = instance
        self.company = company
        self.user = user
        self.password = password
        self.session = requests.Session()
        self.session.headers = headers
        self.token = None

    def _url(self, endpoint):
        return self.base_url.format(self.instance, endpoint)

    def _post(self, url, params=None, json={}):
        if self.token:
            json["token"] = self.token
        self.log.info("url: {}\n json: {}".format(url, json))
        r = self.session.post(url, params=params, json=json)
        r.raise_for_status()
        return r.json()

    def auth(self):
        url = self._url("authenticate")
        payload = {'userName': self.user, 'password': self.password, 'companyName': self.company}
        json = self._post(url, json=payload)
        result = json["AuthenticateResult"]
        if "token" in result:
            self.token = result["token"]

    def get_case_inbox(self):
        """
        {'caseMobileInboxData': {'Rows': [{'CaseId': 51,
                                           'Columns': [{'CaseQuestionTypeId': 1,
                                                        'ColumnColorValue': 0,
                                                        'ColumnName': 'Case ID | Case '
                                                                      'Status',
                                                        'ColumnValue': '51 | In '
                                                                       'Progress',
                                                        'SortIndex': 0},
                                                       {'CaseQuestionTypeId': 100,
                                                        'ColumnColorValue': 0,
                                                        'ColumnName': 'First Name',
                                                        'ColumnValue': '',
                                                        'SortIndex': 1},
                                                       {'CaseQuestionTypeId': 100,
                                                        'ColumnColorValue': 0,
                                                        'ColumnName': 'Last Name',
                                                        'ColumnValue': '',
                                                        'SortIndex': 2},
                                                       {'CaseQuestionTypeId': 100,
                                                        'ColumnColorValue': 0,
                                                        'ColumnName': 'Issue category',
                                                        'ColumnValue': '',
                                                        'SortIndex': 3},
                                                       {'CaseQuestionTypeId': 19,
                                                        'ColumnColorValue': 1,
                                                        'ColumnName': 'Time To Close',
                                                        'ColumnValue': '8d 6h',
                                                        'SortIndex': 4}],
                                           'IsActionPlan': False,
                                           'NewMessageCount': 0,
                                           'RespondentId': 186692,
                                           'SortIndex': 0,
                                           'StatusName': 'In Progress'},
                                          {'CaseId': 50,
                                           'Columns': [{'CaseQuestionTypeId': 1,
                                                        'ColumnColorValue': 0,
                                                        'ColumnName': 'Case ID | Case '
                                                                      'Status',
                                                        'ColumnValue': '50 | New',
                                                        'SortIndex': 0},
                                                       {'CaseQuestionTypeId': 100,
                                                        'ColumnColorValue': 0,
                                                        'ColumnName': 'First Name',
                                                        'ColumnValue': '',
                                                        'SortIndex': 1},
                                                       {'CaseQuestionTypeId': 100,
                                                        'ColumnColorValue': 0,
                                                        'ColumnName': 'Last Name',
                                                        'ColumnValue': '',
                                                        'SortIndex': 2},
                                                       {'CaseQuestionTypeId': 100,
                                                        'ColumnColorValue': 0,
                                                        'ColumnName': 'Issue category',
                                                        'ColumnValue': '',
                                                        'SortIndex': 3},
                                                       {'CaseQuestionTypeId': 19,
                                                        'ColumnColorValue': 1,
                                                        'ColumnName': 'Time To Close',
                                                        'ColumnValue': '8d 7h',
                                                        'SortIndex': 4}],
                                           'IsActionPlan': False,
                                           'NewMessageCount': 0,
                                           'RespondentId': 186690,
                                           'SortIndex': 1,
                                           'StatusName': 'New'}],
                                 'TotalNewMessageCount': 0},
         'statusMessage': 'Successful'}
        """
        url = self._url("getMobileCaseInboxItems")
        json = self._post(url)
        rows = json["GetMobileCaseInboxItemsResult"]["caseMobileInboxData"]["Rows"]
        case_ids = []
        fieldnames = []
        cases = []
        for row in rows:
            case = {}
            for key, val in row.items():
                # special case for the nested list of n columns
                if key == "Columns":
                    for column in val:
                        column_name = column["ColumnName"]
                        if column_name not in fieldnames:
                            fieldnames.append(column_name)
                        case[column_name] = column["ColumnValue"]
                else:
                    if key not in fieldnames:
                        fieldnames.append(key)
                    if key == "CaseId":
                        case_ids.append(val)
                    case[key] = val
            cases.append(case)

        return Inbox(ids=case_ids, fieldnames=fieldnames, cases=cases)

    def get_case(self, case_id):
        url = self._url("getCaseView")
        payload = {'token': self.token, 'caseId': case_id}
        json = self._post(url, json=payload)
        case = Case(json["GetCaseViewResult"])

        return case


class Case:
    """
    'viewValues': {'ActivityNotes': [],
                'AlertName': 'detractor ',
                'CaseId': 51,
                'CasePriorityId': 29,
                'CaseRootCauseAnswers': [],
                'CaseRootCauseTreeIds': ['j7_3', 'j3_4'],
                'CaseStatusId': 30,
                'CaseWatchers': [],
                'CurrentUserId': 'd9c248c6-a4ae-4f8d-b145-5ad2de264a32',
                'DateClosed': '/Date(-62135427600000+0100)/',
                'DateClosedFormatted': '',
                'DateSubmitted': '/Date(1485780932517+0100)/',
                'DateSubmittedFormatted': '2017-01-30T13:55:32.517+01:00',
                'DisableCaseReassignmentNotifications': False,
                'DisableCaseWatcherNotifications': False,
                'FirstName': 'Anthony',
                'ItemAnswers': [],
                'LastName': 'Wright',
                'ModifiedDate': '/Date(1486501778417+0100)/',
                'ModifiedDateFormatted': '2017-02-07T22:09:38.417+01:00',
                'OwnerFullName': 'Anthony Wright',
                'OwnerUserId': 'd9c248c6-a4ae-4f8d-b145-5ad2de264a32',
                'ProgramName': 'Samsung Case Management ',
                'RespondentHash': None,
                'RespondentId': 186692,
                'SourceName': '',
                'SourceResponses': [],
                'SourceValues': [],
                'SurveyId': 40,
                'SurveyName': 'Samsung Survey',
                'TimeToClose': 733967,
                'TimeToCloseColor': 1,
                'TimeToCloseDays': 8,
                'TimeToCloseDisplay': '8d 11h',
                'TimeToCloseGoal': 259200,
                'TimeToCloseGoalDays': 3,
                'TimeToCloseGoalDisplay': '3d 0h',
                'TimeToCloseGoalHours': 0,
                'TimeToCloseHours': 11,
                'TimeToRespond': 104187,
                'TimeToRespondColor': 1,
                'TimeToRespondDays': 1,
                'TimeToRespondDisplay': '1d 4h',
                'TimeToRespondGoal': 86400,
                'TimeToRespondGoalDays': 1,
                'TimeToRespondGoalDisplay': '1d 0h',
                'TimeToRespondGoalHours': 0,
                'TimeToRespondHours': 4,
                'WatcherType': 0}
    """

    def __init__(self, case_view):
        values = case_view["viewValues"]
        self.case_id = values["CaseId"]
        self.alert_name = values["AlertName"]
        self.owner = values["OwnerFullName"]
        self.time_to_close = values["TimeToCloseDisplay"]
        self.time_to_close_goal = values["TimeToCloseGoalDisplay"]
        self.time_to_respond = values["TimeToRespondDisplay"]
        self.time_to_respond_goal = values["TimeToRespondGoalDisplay"]
        self.status_id = values["CaseStatusId"]
        self.priority_id = values["CasePriorityId"]
        self.status = ""
        self.priority = ""
        self.activity_notes = []
        self.items = []
        self.source_responses = []

        items = case_view["caseView"]["CaseViewItems"]
        self._parse_items(items)

        self._parse_item_answers(values["ItemAnswers"])
        self._parse_root_cause_answers(values["CaseRootCauseAnswers"])
        self._parse_activity_notes(values["ActivityNotes"])
        self._parse_source_responses(values["SourceResponses"])
        self.status = self._lookup_item_dropdown_value(Item.STATUS, self.status_id)
        self.priority = self._lookup_item_dropdown_value(Item.PRIORITY, self.priority_id)

    def __str__(self):
        items = "\n".join([str(a) for a in self.items])
        activity_notes = "\n".join([str(n) for n in self.activity_notes])
        source_responses = "\n".join([str(s) for s in self.source_responses])
        return "id:{} owner:{} status:{} priority:{}\nACTIVITY NOTES:\n{}\n\nITEMS:\n{}\n\nRESPONSES:\n{}".format(self.case_id,
                                                                                                                  self.owner,
                                                                                                                  self.status,
                                                                                                                  self.priority,
                                                                                                                  activity_notes,
                                                                                                                  items,
                                                                                                                  source_responses)

    @property
    def dict(self):
        """ Returns a dictionary representation of the standard properties, source_responses, and items with a display_answer

        """
        COL_CASE_ID = "Case ID"
        COL_OWNER = "Owner"
        COL_TIME_TO_CLOSE = "Time To Close"
        COL_TIME_TO_CLOSE_GOAL = "Time to Goal Close"
        COL_TIME_TO_RESPOND = "Time To Respond"
        COL_TIME_TO_RESPOND_GOAL = "Time To Goal Respond"
        COL_STATUS = "Status"
        COL_PRIORITY = "Priority"
        COL_ACTIVITY_NOTES = "Activity Notes"

        case = {COL_CASE_ID: self.case_id,
                COL_OWNER: self.owner,
                COL_TIME_TO_CLOSE: self.time_to_close,
                COL_TIME_TO_CLOSE_GOAL: self.time_to_close_goal,
                COL_TIME_TO_RESPOND: self.time_to_respond,
                COL_TIME_TO_RESPOND_GOAL: self.time_to_respond_goal,
                COL_STATUS: self.status,
                COL_PRIORITY: self.priority,
                COL_ACTIVITY_NOTES: ", ".join(str(n) for n in self.activity_notes)}

        for item in self.items:
            if item.display_answer:
                case[item.case_item_text] = item.display_answer

        for source_response in self.source_responses:
            case[source_response.question_text] = source_response.answer_text

        return case

    def _lookup_item_dropdown_value(self, case_question_type_id, value):
        item = self._find_item_by_type(case_question_type_id)
        dropdown = item._find_dropdown(value)
        return dropdown.text

    def _parse_items(self, items):
        for item_dict in items:
            item = Item(item_dict)
            self.items.append(item)

    def _parse_activity_notes(self, activity_notes):
        for note_dict in activity_notes:
            self.activity_notes.append(ActivityNote(note_dict))

    def _parse_item_answers(self, item_answers):
        for item_answer_dict in item_answers:
            item = next(x for x in self.items if x.case_item_id == item_answer_dict["CaseItemId"])
            if item:
                item.add_answer(item_answer_dict)

    def _parse_root_cause_answers(self, root_cause_answers):
        for root_cause_answer_dict in root_cause_answers:
            item = self._find_item(root_cause_answer_dict["CaseItemId"])
            if item:
                item.add_root_cause_answer(root_cause_answer_dict)

    def _parse_source_responses(self, source_responses):
        for source_response_dict in source_responses:
            self.source_responses.append(SourceResponse(source_response_dict))

    def _find_item(self, case_item_id):
        return next(x for x in self.items if x.case_item_id == case_item_id)

    def _find_item_by_type(self, case_question_type_id):
        return next(x for x in self.items if x.case_question_type_id == case_question_type_id)


class Item:
    """
    'CaseViewItems': [{'CaseId': 51,
                     'CaseItemId': 10154,
                     'CaseItemText': 'Time to respond',
                     'CaseProgramId': 11,
                     'CaseQuestionTypeId': 18,
                     'DefaultValue': None,
                     'DropdownValues': [],
                     'FormatString': '{"labelFontWeight":400}',
                     'IsEmailAddress': False,
                     'IsPhoneNumber': False,
                     'NeededToClose': False,
                     'ResourceKey': 'caseitem.text10154',
                     'RootCauseValues': [],
                     'SourceScaleId': 0,
                     'isGroupParent': False,
                     'mobileIndex': 0,
                     'parentItemID': 0,
                     'showTimeField': False}]
    """

    def __init__(self, values):
        self.case_item_id = values["CaseItemId"]
        self.case_question_type_id = values["CaseQuestionTypeId"]
        self.case_item_text = values["CaseItemText"]
        self.dropdown_values = []
        self.root_cause_values = []
        self.root_cause_answers = []
        self.answer = None
        self.display_answer = ""

        self._parse_dropdown_values(values["DropdownValues"])
        self._parse_root_cause_values(values["RootCauseValues"])
        self._build_root_cause_tree()

    def __str__(self):
        dropdowns = ", ".join([str(d) for d in self.dropdown_values])
        root_causes = self._draw_root_cause_tree()
        root_causes_answers = self._draw_root_cause_answers()

        return """\n==========\nitem_id:{} question_type: {} text:{} display:{}\n
dropdown:\n{}\n
rootcauses:\n{}\n
rootcause_answers:\n{}\n
answer:\n{}""".format(self.case_item_id,
                      self.case_question_type_id,
                      self.case_item_text,
                      self.display_answer,
                      dropdowns,
                      root_causes,
                      root_causes_answers,
                      self.answer)

    def _draw_root_cause_tree(self):
        roots = [r for r in self.root_cause_values if r.is_root is True]
        tree = ""
        for root in roots:
            for pre, _, node in RenderTree(root):
                tree = "{}{}{}\n".format(tree, pre, node.root_cause_name)

        return tree

    def _draw_root_cause_answers(self):
        answers = ""
        leaf_answers = [a for a in self.root_cause_answers if a.root_cause.is_leaf]
        for leaf_answer in leaf_answers:
            leaf = leaf_answer.root_cause.root_cause_name
            ancestors = " > ".join([c.root_cause_name for c in leaf_answer.root_cause.anchestors])
            answers = "{}{} > {}, ".format(answers, ancestors, leaf)

        return answers

    def _parse_dropdown_values(self, dropdown_values):
        for dropdown_dict in dropdown_values:
            dropdown = Dropdown(dropdown_dict)
            self.dropdown_values.append(dropdown)

    def _parse_root_cause_values(self, root_cause_values):
        for root_cause_dict in root_cause_values:
            root_cause = RootCause(root_cause_dict)
            self.root_cause_values.append(root_cause)

    def _build_root_cause_tree(self):
        # assign parents
        for root_cause in self.root_cause_values:
            if root_cause.parent_tree_id != "#":
                root_cause.parent = self._find_root_cause(root_cause.parent_tree_id)

    def _find_root_cause(self, tree_id):
        return next(r for r in self.root_cause_values if r.tree_id == tree_id)

    # case_question_type_ids
    CASE_ID = 1
    PROGRAM_NAME = 2
    CREATED_DATE = 3
    STATUS = 4
    PRIORITY = 5
    ROOT_CAUSE = 6
    ACTIVITY_NOTES = 7
    OWNER = 9
    ALERT_NAME = 10
    SHORT_TEXT_BOX = 11
    LONG_TEXT_BOX = 12
    DROPDOWN = 13
    SURVEY_EXCERPT = 15
    CLOSED_DATE = 16
    SURVEY_NAME = 17
    TIME_TO_RESPOND = 18
    TIME_TO_CLOSE = 19
    EXPLANATION_TEXT = 20
    DIVIDER = 21
    WATCHERS = 22
    LAST_MODIFIED = 25
    DATE_PICKER = 26
    NUMERIC = 27

    def _find_dropdown(self, value):
        return next(x for x in self.dropdown_values if x.id == value)

    def add_answer(self, values):
        self.answer = Answer(values)
        if self.case_question_type_id in [self.SHORT_TEXT_BOX, self.LONG_TEXT_BOX, self.DATE_PICKER]:
            self.display_answer = self.answer.text_value
        elif self.case_question_type_id == self.NUMERIC:
            self.display_answer = self.answer.double_value
        elif self.case_question_type_id == self.DROPDOWN:
            dropdown = self._find_dropdown(self.answer.int_value)
            self.display_answer = dropdown.text

    def add_root_cause_answer(self, values):
        answer = RootCauseAnswer(values)
        answer.root_cause = self._find_root_cause(answer.tree_id)
        self.root_cause_answers.append(answer)
        self.display_answer = self._draw_root_cause_answers()


class ActivityNote:
    """
    'ActivityNotes': [{
                    'ActivityNote': 'this is a second activity note',
                    'ActivityNoteDate': '/Date(1486501766713+0100)/',
                    'CaseActivityNoteId': 15,
                    'CaseId': 51,
                    'FirstName': 'Anthony',
                    'FullName': 'Anthony Wright',
                    'HashCode': 'ACDBEF5A470DD47E3320C12565DD6C3D6592423A',
                    'LastName': 'Wright',
                    'NoteFile': None,
                    'UserId': 'd9c248c6-a4ae-4f8d-b145-5ad2de264a32'
                    }]
    """

    def __init__(self, values):
        self.note = values["ActivityNote"]
        self.date = values["ActivityNoteDate"]
        self.full_name = values["FullName"]

    def __str__(self):
        return "{}@{}: {}".format(self.full_name, self.date, self.note)


class Dropdown:
    """
    'DropdownValues': [{
                        'Id': -1,
                        'LocalizedLabel': None,
                        'Text': 'Select One'
                      }]
    """

    def __init__(self, values):
        self.id = values["Id"]
        self.text = values["Text"]

    def __str__(self):
        return "{}:{}".format(self.id, self.text)


class RootCause(NodeMixin):
    """
    'RootCauseValues': [{
                      'AllowOtherNode': True,
                      'CaseItemId': 10172,
                      'CaseRootCauseId': 50,
                      'ParentTreeId': '#',
                      'RootCauseName': 'Product',
                      'TreeId': 'j7_1'
                      }]
    """

    def __init__(self, values):
        self.case_item_id = values["CaseItemId"]
        self.case_root_cause_id = values["CaseRootCauseId"]
        self.root_cause_name = values["RootCauseName"]
        self.parent_tree_id = values["ParentTreeId"]
        self.tree_id = values["TreeId"]
        self.parent = None

    def __str__(self):
        return "item_id:{} root_cause_id:{} root_cause_name:{} parent_tree_id:{} tree_id:{}".format(self.case_item_id,
                                                                                                    self.case_root_cause_id,
                                                                                                    self.root_cause_name,
                                                                                                    self.parent_tree_id,
                                                                                                    self.tree_id)


class RootCauseAnswer:
    """
    'CaseRootCauseAnswers': [{'CaseItemId': 10172,
                              'CaseRootCauseId': 51,
                              'TreeId': 'j7_3'}]
    """

    def __init__(self, values):
        self.case_item_id = values["CaseItemId"]
        self.case_root_cause_id = values["CaseRootCauseId"]
        self.tree_id = values["TreeId"]
        self.root_cause = None

    def __str__(self):
        return "item_id:{} root_cause_id:{} tree_id:{}".format(self.case_item_id, self.case_root_cause_id, self.tree_id)


class Answer:
    """
    {'BoolValue': False,
    'CaseId': 51,
    'CaseItemAnswerId': 23,
    'CaseItemId': 10171,
    'CaseQuestionTypeId': 12,
    'DoubleValue': 0,
    'IntValue': 0,
    'IsEmpty': False,
    'TextValue': 'I called the customer and fixed the problem',
    'TimeValue': '/Date(-62135427600000+0100)/'}
    """

    def __init__(self, values):
        self.case_item_answer_id = values["CaseItemAnswerId"]
        self.case_item_id = values["CaseItemId"]
        self.case_question_type_id = values["CaseQuestionTypeId"]
        self.is_empty = values["IsEmpty"]
        self.bool_value = values["BoolValue"]
        self.double_value = values["DoubleValue"]
        self.int_value = values["IntValue"]
        self.text_value = values["TextValue"]
        self.time_value = values["TimeValue"]

    def __str__(self):
        return "id:{} question_type:{} bool:{} double:{} int:{} text:{} time:{}".format(self.case_item_answer_id,
                                                                                        self.case_question_type_id,
                                                                                        self.bool_value,
                                                                                        self.double_value,
                                                                                        self.int_value,
                                                                                        self.text_value,
                                                                                        self.time_value)


class SourceResponse:
    """
    'SourceResponses': [{
                         'Key': 10204,
                         'Value': {
                                  'AnswerText': '3',
                                  'DisplayType': 3,
                                  'QuestionText': 'Please rate the the level of overall service provided.'
                                 }
                        }]
    """

    def __init__(self, values):
        self.case_item_id = values["Key"]
        self.question_text = values["Value"]["QuestionText"]
        self.answer_text = values["Value"]["AnswerText"]

    def __str__(self):
        return "item_id:{} text:{} answer:{}".format(self.case_item_id, self.question_text, self.answer_text)

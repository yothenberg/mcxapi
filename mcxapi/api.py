import logging
import requests
import re
from datetime import datetime, timezone, timedelta

from collections import namedtuple
from anytree import RenderTree, NodeMixin

Inbox = namedtuple('Inbox', 'ids fieldnames cases')


def parse_date(date):
    # Weird date format /Date(milliseconds-since-epoch-+tzoffset)/
    # /Date(1486742990423-0600)/
    # /Date(1486664366563+0100)/
    r = re.compile(r'/Date\((\d+)([-+])(\d{2,2})(\d{2,2})\)/')
    m = r.match(date)
    if m is None:
        return "Unknown Date Format"
    else:
        milliseconds, sign, tzhours, tzminutes = m.groups()
        seconds = int(milliseconds) / 1000.0
        sign = -1 if sign == '-' else 1
        tzinfo = timezone(sign * timedelta(hours=int(tzhours), minutes=int(tzminutes)))
        return datetime.fromtimestamp(seconds, tzinfo).strftime('%Y-%m-%d %H:%M%z')


class McxApi:
    BASE_URL = "https://{}.allegiancetech.com/CaseManagement.svc/{}"
    TIMEOUT = 30
    RETRY = 3
    PASSWORD_KEY = "password"
    TOKEN_KEY = "token"

    def __init__(self, instance, company, user, password, headers=None):
        self.instance = instance
        self.company = company
        self.user = user
        self.password = password
        self.session = requests.Session()
        self.session.headers = headers
        self.token = None

    def _sanitize_json_for_logging(self, json):
        json_copy = json.copy()
        if self.PASSWORD_KEY in json_copy:
            json_copy[self.PASSWORD_KEY] = "*****"
        if self.TOKEN_KEY in json:
            json_copy[self.TOKEN_KEY] = "*****"

        return json_copy

    def _url(self, endpoint):
        return self.BASE_URL.format(self.instance, endpoint)

    def _post(self, url, params=None, json={}):
        if self.token:
            json[self.TOKEN_KEY] = self.token
        logging.info("POST: url: {} json: {}".format(url, self._sanitize_json_for_logging(json)))
        r = self.session.post(url, params=params, json=json, timeout=self.TIMEOUT)
        r.raise_for_status()
        return r.json()

    def auth(self):
        url = self._url("authenticate")
        payload = {'userName': self.user, self.PASSWORD_KEY: self.password, 'companyName': self.company}
        json = self._post(url, json=payload)
        result = json["AuthenticateResult"]
        if "token" in result:
            self.token = result["token"]

    def get_case_inbox(self):
        """ Fetches active cases assigned to the user
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
        """ Fetches detailed information about a case
        """
        url = self._url("getCaseView")
        payload = {'caseId': case_id}
        json = self._post(url, json=payload)
        case = Case(json["GetCaseViewResult"])

        return case


class Case:
    """ A Case
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
        """ Returns a dictionary representation of the standard properties, source_responses, and items with an answer

        """
        COL_CASE_ID = "Case ID"
        COL_OWNER = "Owner"
        COL_TIME_TO_CLOSE = "Time To Close"
        COL_TIME_TO_CLOSE_GOAL = "Time to Goal Close"
        COL_TIME_TO_RESPOND = "Time To Respond"
        COL_TIME_TO_RESPOND_GOAL = "Time To Goal Respond"
        COL_STATUS = "Status"
        COL_PRIORITY = "Priority"

        case = {COL_CASE_ID: self.case_id,
                COL_OWNER: self.owner,
                COL_TIME_TO_CLOSE: self.time_to_close,
                COL_TIME_TO_CLOSE_GOAL: self.time_to_close_goal,
                COL_TIME_TO_RESPOND: self.time_to_respond,
                COL_TIME_TO_RESPOND_GOAL: self.time_to_respond_goal,
                COL_STATUS: self.status,
                COL_PRIORITY: self.priority}

        for item in self.items:
            if item.answer or item.root_cause_answers:
                case[item.case_item_text] = item.display_answer

        # Activity notes are exported one per column
        i = 1
        COL_ACTIVITY_NOTES = "Activity Note {}"
        for activity_note in self.activity_notes:
            case[COL_ACTIVITY_NOTES.format(i)] = "{} @ {}: {}".format(activity_note.full_name,
                                                                      parse_date(activity_note.date),
                                                                      activity_note.note)
            i += 1

        for source_response in self.source_responses:
            # sometimes the source responses don't have a question text so we use the case_item_id for the column header
            if source_response.question_text:
                case[source_response.question_text] = source_response.answer_text
            else:
                case[str(source_response.case_item_id)] = source_response.answer_text

        return case

    def _lookup_item_dropdown_value(self, case_question_type_id, value):
        item = self._find_item_by_type(case_question_type_id)
        if item:
            dropdown = item._find_dropdown(value)
            return dropdown.text
        else:
            return None

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
        try:
            item = next(x for x in self.items if x.case_item_id == case_item_id)
        except StopIteration:
            return None

        return item

    def _find_item_by_type(self, case_question_type_id):
        try:
            item = next(x for x in self.items if x.case_question_type_id == case_question_type_id)
        except StopIteration:
            return None

        return item


class Item:
    """
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
            answers = "{}{} > {}\n".format(answers, ancestors, leaf)

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
        if self.answer.is_empty:
            self.display_value = ""
        elif self.case_question_type_id in [self.SHORT_TEXT_BOX, self.LONG_TEXT_BOX, self.DATE_PICKER]:
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
    def __init__(self, values):
        self.note = values["ActivityNote"]
        self.date = values["ActivityNoteDate"]
        self.full_name = values["FullName"]

    def __str__(self):
        return "{}@{}: {}".format(self.full_name, self.date, self.note)


class Dropdown:
    def __init__(self, values):
        self.id = values["Id"]
        self.text = values["Text"]

    def __str__(self):
        return "{}:{}".format(self.id, self.text)


class RootCause(NodeMixin):
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
    def __init__(self, values):
        self.case_item_id = values["CaseItemId"]
        self.case_root_cause_id = values["CaseRootCauseId"]
        self.tree_id = values["TreeId"]
        self.root_cause = None

    def __str__(self):
        return "item_id:{} root_cause_id:{} tree_id:{}".format(self.case_item_id, self.case_root_cause_id, self.tree_id)


class Answer:
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
    def __init__(self, values):
        self.case_item_id = values["Key"]
        self.question_text = values["Value"]["QuestionText"]
        self.answer_text = values["Value"]["AnswerText"]

    def __str__(self):
        return "item_id:{} text:{} answer:{}".format(self.case_item_id, self.question_text, self.answer_text)

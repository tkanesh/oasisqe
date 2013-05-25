# -*- coding: utf-8 -*-

# This code is under the GNU Affero General Public License
# http://www.gnu.org/licenses/agpl-3.0.html

""" Courses.py
    Handle course related operations.
"""
from oasis.lib import Topics, Groups

from oasis.lib.DB import run_sql, dbpool, MC
from logging import log, ERROR
import datetime

# WARNING: name and title are stored in the database as: title, description


def getVersion():
    """ Fetch the current version of the course table.
        This will be incremented when anything in the courses table is changed.
        The idea is that while the version hasn't changed, course information
        can be cached in memory.
    """
    key = "coursetable-version"
    obj = MC.get(key)
    if obj:
        return int(obj)
    ret = run_sql("SELECT last_value FROM courses_version_seq;")
    if ret:
        MC.set(key, int(ret[0][0]))
        return int(ret[0][0])
    log(ERROR, "Error fetching Courses version.")
    return -1


def incrementVersion():
    """ Increment the course table version."""
    key = "coursetable-version"
    MC.delete(key)
    ret = run_sql("SELECT nextval('courses_version_seq');")
    if ret:
        MC.set(key, int(ret[0][0]))
        return int(ret[0][0])
    log(ERROR, "Error incrementing Courses version.")
    return -1


def setName(course_id, name):
    """ Set the name of a course."""
    assert isinstance(course_id, int)
    assert isinstance(name, str) or isinstance(name, unicode)
    incrementVersion()
    run_sql("UPDATE courses SET title=%s WHERE course=%s;", (name, course_id))
    key = "course-%s-name" % course_id
    MC.delete(key)


def setTitle(course_id, title):
    """ Set the title of a course."""
    assert isinstance(course_id, int)
    assert isinstance(title, str) or isinstance(title, unicode)
    incrementVersion()
    run_sql("UPDATE courses SET description=%s WHERE course=%s;", (title, course_id))
    key = "course-%s-title" % course_id
    MC.delete(key)


def getActive(course_id):
    """ Fetch the active flag"""
    assert isinstance(course_id, int)
    key = "course-%s-active" % course_id
    obj = MC.get(key)
    if not obj is None:
        return obj
    ret = run_sql("SELECT active FROM courses WHERE course=%s;", (course_id,))
    if ret:
        MC.set(key, ret[0][0])
        return ret[0][0]
    log(ERROR, "Request for active flag of unknown course %s." % course_id)
    return None


def setActive(course_id, active):
    """ Set the active flag of a course."""
    assert isinstance(course_id, int)
    assert isinstance(active, bool)
    if active:
        val = 1
    else:
        val = 0
    run_sql("UPDATE courses SET active=%s WHERE course=%s;", (val, course_id))
    incrementVersion()
    key = "course-%s-active" % course_id
    MC.delete(key)
    key = "courses-active"
    MC.delete(key)


def setEnrolType(course_id, enrol_type):
    """ Set the enrolment type of a course."""
    assert isinstance(course_id, int)
    assert isinstance(enrol_type, str) or isinstance(enrol_type, unicode)

    run_sql("UPDATE courses SET enrol_type=%s WHERE course=%s;", (enrol_type, course_id))
    incrementVersion()


def setRegistration(course_id, registration):
    """ Set the registration type of a course."""
    assert isinstance(course_id, int)
    assert isinstance(registration, str) or isinstance(registration, unicode)

    run_sql("UPDATE courses SET registration=%s WHERE course=%s;", (registration, course_id))
    incrementVersion()


def setPracticeVisibility(cid, visibility):
    """ Who can do practice questions."""
    assert isinstance(cid, int)
    assert isinstance(visibility, str) or isinstance(visibility, unicode)

    run_sql("UPDATE courses SET practice_visibility=%s WHERE course=%s;", (visibility, cid))
    incrementVersion()


def setAssessVisibility(cid, visibility):
    """ Who can do assessments."""
    assert isinstance(cid, int)
    assert isinstance(visibility, str) or isinstance(visibility, unicode)

    run_sql("UPDATE courses SET assess_visibility=%s WHERE course=%s;", (visibility, cid))
    incrementVersion()


def setEnrolLocation(cid, enrol_location):
    """ Set the enrolment location of a course."""
    assert isinstance(cid, int)
    assert isinstance(enrol_location, str) or isinstance(enrol_location, unicode)

    run_sql("UPDATE courses SET enrol_location=%s WHERE course=%s;", (enrol_location, cid))
    incrementVersion()


def setEnrolFreq(cid, enrol_freq):
    """ Set the enrolment sync frequency of a course in minutes."""
    assert isinstance(cid, int)
    assert isinstance(enrol_freq, int)

    run_sql("UPDATE courses SET enrol_freq=%s WHERE course=%s;", (enrol_freq, cid))
    incrementVersion()


def getUsersInCourse(course):
    """ Return a list of users in the course"""
    groups = get_groups(course)
    allusers = []
    for group in groups:
        allusers += Groups.getUsersInGroup(group)
    return allusers


def getInfoAll():
    """ Return a summary of all active courses, sorted by name
        [position] = { 'id':id, 'name':name, 'title':title }
    """
    ret = run_sql(
        """SELECT course, title, description, owner, active, type,
                  enrol_type, enrol_location, enrol_freq, registration,
                  practice_visibility, assess_visibility
             FROM courses
             WHERE active='1'
             ORDER BY title ;""")
    info = {}
    if ret:
        count = 0
        for row in ret:
            info[count] = {
                'id': int(row[0]),
                'name': row[1],
                'title': row[2],
                'owner': row[3],
                'active': row[4],
                'type': row[5],
                'enrol_type': row[6],
                'enrol_location': row[7],
                'enrol_freq': row[8],
                'registration': row[9],
                'practice_visibility': row[10],
                'assess_visibility': row[11]
            }
            # Defaults added since database was created
            if not row['enrol_location']:
                row['enrol_location'] = ""
            if not row['practice_visibility']:
                row['practice_visibility'] = "all"
            if not row['assess_visibility']:
                row['assess_visibility'] = "all"
            count += 1
    return info


def getAll(only_active=True):
    """ Return a list of all courses in the system."""
    if only_active:
        sql = """SELECT course FROM courses WHERE active=1 ORDER BY title;"""
        key = "courses-active"
    else:
        sql = """SELECT course FROM courses ORDER BY title;"""
        key = "courses-all"
    obj = MC.get(key)
    if obj:
        return obj
    ret = run_sql(sql)
    if ret:
        courses = [int(row[0]) for row in ret]
        MC.set(key, courses)
        return courses
    return []


def getFullCourseDict():
    """ Return a summary of all courses, keyed by course id
        [id] = { 'id':id, 'name':name, 'title':title }
    """
    ret = run_sql(
        """SELECT course, title, description, owner, active, type,
                  enrol_type, enrol_location, enrol_freq, registration,
                  practice_visibility, assess_visibility
             FROM courses;""")
    cdict = {}
    if ret:
        for row in ret:
            course = {
                'id': int(row[0]),
                'name': row[1],
                'title': row[2],
                'owner': row[3],
                'active': row[4],
                'type': row[5],
                'enrol_type': row[6],
                'enrol_location': row[7],
                'enrol_freq': row[8],
                'registration': row[9],
                'practice_visibility': row[10],
                'assess_visibility': row[11]
            }
            if course['enrol_location'] is None:
                course['enrol_location'] = ''
            if not course['practice_visibility']:
                course['practice_visibility'] = "all"
            if not course['assess_visibility']:
                course['assess_visibility'] = "all"
            cdict[int(row[0])] = course
    return cdict


def create(name, description, owner, coursetype):
    """ Add a course to the database."""
    conn = dbpool.begin()
    conn.run_sql("""INSERT INTO courses (title, description, owner, type)
                    VALUES (%s, %s, %s, %s);""",
                    (name, description, owner, coursetype))
    res = conn.run_sql("SELECT currval('courses_course_seq')")
    dbpool.commit(conn)
    incrementVersion()
    key = "courses-active"
    MC.delete(key)
    key = "courses-all"
    MC.delete(key)
    if res:
        return int(res[0][0])
    log(ERROR,
        "create('%s','%s',%d,%d) Fail" % (name, description, owner, coursetype))
    return 0


def get_groups(course):
    """ Return a list of groups currently attached to this course."""
    # TODO: need to figure out how to incorporate semester codes/timing.
    sql = "SELECT groupid FROM groupcourses WHERE active='1' AND course = %s;"
    params = (course, )
    ret = run_sql(sql, params)
    groups = []
    if ret:
        groups = [row[0] for row in ret]
    return groups


def getCourseGroupMap(only_active=True):
    """ Return a dictionary mapping course ids to (multiple) group ids.
        eg. { 5: [1,2,3], 6: [2,3] }
        says that groups 1,2,3 are associated with course 5,and 2,3 with
        course 6.
        if only_active is set to False, will include inactive courses.
    """
    courses = getAll(only_active)
    coursemap = {}
    for course in courses:
        coursemap[course] = get_groups(course)
    return coursemap


def add_group(group_id, course_id):
    """ Add a group to a course."""
    sql = "INSERT INTO groupcourses (groupid, active, course) " \
          "VALUES (%s, %s, %s);"
    params = (group_id, 1, course_id)
    run_sql(sql, params)


# TODO most of this should be in Topics. Especially the SQL parts, so it's
#  easier to cache without getting confused.
def getTopicsInfoAll(course, archived=2, numq=True):
    """ Return a summary of all topics in the course.
        if archived=0, only return non archived courses
        if archived=1, only return archived courses
        if archived=2, return all courses
        if numq is true then include the number of questions in the topic
    """
    ret = None
    if archived == 0:
        ret = run_sql("""SELECT topic, title, position, visibility, archived
                         FROM topics
                         WHERE course=%s
                           AND (archived='0' OR archived IS NULL)
                         ORDER BY position, topic;""", (course,))
    elif archived == 1:
        ret = run_sql("""SELECT topic, title, position, visibility, archived
                         FROM topics
                         WHERE course=%s
                           AND archived='1'
                         ORDER BY position, topic;""", (course,))
    elif archived == 2:
        ret = run_sql("""SELECT topic, title, position, visibility, 0
                         FROM topics
                         WHERE course=%s
                         ORDER BY position, topic;""", (course,))
    info = {}
    if ret:
        count = 0
        for row in ret:
            info[count] = {'id': int(row[0]),
                           'title': row[1],
                           'position': row[2],
                           'visibility': row[3],
                           'archived': row[4]}
            if numq:
                info[count]['numquestions'] = Topics.get_num_qs(int(row[0]))
            count += 1
    else:  # we probably don't have the archived flag in the Db yet
        ret = run_sql(
            """SELECT topic, title, visibility
               FROM topics
               WHERE course=%s
               ORDER BY position, topic;""", (course,))
        if ret:
            count = 0
            for row in ret:
                info[count] = {'id': int(row[0]),
                               'title': row[1],
                               'visibility': row[2]}
                if numq:
                    info[count]['numquestions'] = Topics.get_num_qs(int(row[0]))
                count += 1
    return info


def getTopics(cid):
    """ Return a list of all topics in the course."""
    key = "course-%s-topics" % cid
    obj = MC.get(key)
    if obj:
        return obj
    sql = "SELECT topic FROM topics WHERE course=%s ORDER BY position;"
    params = (cid,)
    ret = run_sql(sql, params)
    if ret:
        topics = [row[0] for row in ret]
        MC.set(key, topics)
        return topics
    MC.set(key, [])
    return []


def getExams(cid, previous_years=False):
    """ Return a list of all assessments in the course."""
    assert isinstance(cid, int)
    assert isinstance(previous_years, bool)
    if not previous_years:
        now = datetime.datetime.now()
        year = now.year
        sql = """SELECT exam
                 FROM exams
                 WHERE course=%s
                   AND archived='0'
                   AND "end" > '%s-01-01';"""
        params = (cid, year)
    else:
        sql = """SELECT exam FROM exams WHERE course=%s;"""
        params = (cid,)
    ret = run_sql(sql, params)
    if ret:
        exams = [int(row[0]) for row in ret]
        return exams
    return []

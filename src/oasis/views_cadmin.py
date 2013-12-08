# -*- coding: utf-8 -*-

# This code is under the GNU Affero General Public License
# http://www.gnu.org/licenses/agpl-3.0.html

""" Course admin related pages
"""

import os
from datetime import datetime

from logging import log, ERROR

from flask import render_template, session, request, redirect, \
    abort, url_for, flash, make_response

from oasis import db
from oasis.lib import OaConfig, DB, \
    Setup, CourseAdmin, Util, Assess, Spreadsheets
from oasis.models.User import User
from oasis.models.Topic import Topic
from oasis.models.Course import Course
from oasis.models.Permission import Permission

MYPATH = os.path.dirname(__file__)

from oasis.lib.Util import date_from_py2js
from oasis.lib import External
from oasis.models.Group import Group
from oasis.models.Exam import Exam

from oasis import app
from .lib.Util import require_course_perm, require_perm


@app.route("/cadmin/<int:course_id>/top")
@require_course_perm(("questionedit", "viewmarks",
                      "altermarks", "examcreate",
                     "coursecoord", "courseadmin"),
                     redir="setup_top")
def cadmin_top(course_id):
    """ Present top level course admin page """
    course = Course.get(course_id)
    if not course:
        abort(404)

    user_id = session['user_id']
    is_sysadmin = Permission.check_perm(user_id, -1, 'sysadmin')

    topics = course.topics()
    exams = list(Exam.by_course(course))

    exams.sort(key=lambda y: y.start, reverse=True)
    groups = course.groups()
    choosegroups = [group
                    for group in Group.all_groups()
                    if not group.id in groups]
    return render_template(
        "courseadmin_top.html",
        course=course,
        topics=topics,
        exams=exams,
        choosegroups=choosegroups,
        groups=groups,
        is_sysadmin=is_sysadmin
    )


@app.route("/cadmin/<int:course_id>/config")
@require_course_perm(("course_admin", "coursecoord"))
def cadmin_config(course_id):
    """ Allow some course configuration """
    course = Course.get(course_id)
    if not course:
        abort(404)

    user_id = session['user_id']
    is_sysadmin = Permission.check_perm(user_id, -1, 'sysadmin')
    coords = [User.get(perm[0]).id
              for perm in Permission.get_course_perms(course_id)
              if perm[1] == 3]  # course_coord
    groups = course.groups()
    choosegroups = [group
                    for group in Group.all_groups()
                    if not group.id in groups]
    return render_template(
        "courseadmin_config.html",
        course=course,
        coords=coords,
        choosegroups=choosegroups,
        groups=groups,
        is_sysadmin=is_sysadmin
    )


@app.route("/cadmin/<int:course_id>/config_submit", methods=["POST", ])
@require_course_perm(("courseadmin", "coursecoord"))
def cadmin_config_submit(course_id):
    """ Allow some course configuration """
    course = Course.get(course_id)
    if not course:
        abort(404)

    form = request.form

    if "cancel" in form:
        flash("Cancelled edit")
        return redirect(url_for("cadmin_top", course_id=course_id))

    saved = False

    new_name = form.get('name', course['name'])

    existing = Course.get_by_name(new_name)
    if not new_name == course['name']:
        if not (3 <= len(new_name) <= 20):
            flash("Course Name must be between 3 and 20 characters.")
        elif existing:
            flash("There is already a course called %(name)s" % existing)
        else:
            course.name = new_name
            saved = True

    new_title = form.get('title', course['title'])
    if not new_title == course['title']:
        if not (3 <= len(new_title) <= 100):
            flash("Course Title must be between 3 and 100 characters.")
        else:
            Course.title = new_title
            saved = True

    practice_visibility = form.get('practice_visibility',
                                   course.practice_visibility)
    if not (practice_visibility == course.practice_visibility):
        saved = True
        course.practice_visibility = practice_visibility

    if saved:
        flash("Changes Saved")
    else:
        flash("No changes made.")
    return redirect(url_for("cadmin_config", course_id=course_id))


@app.route("/cadmin/<int:course_id>/previousassessments")
@require_course_perm(("questionedit", "viewmarks",
                      "altermarks", "examcreate",
                      "coursecoord", "courseadmin"))
def cadmin_prev_assessments(course_id):
    """ Show a list of older assessments."""
    course = Course.get(course_id)
    if not course:
        abort(404)

    exams = Exam.by_course(course.id, prev_years=True)
    years = [exam.start.year for exam in exams]
    years = list(set(years))
    years.sort(reverse=True)
    exams.sort(key=lambda y: y['start_epoch'])
    return render_template(
        "courseadmin_previousassessments.html",
        course=course,
        exams=exams,
        years=years
    )


@app.route("/cadmin/add_course")
@require_perm('sysadmin')
def cadmin_add_course():
    """ Present page to ask for information about a new course being added
    """
    course = {
        'name': '',
        'title': '',
        'owner': 'admin',
        'coursetemplate': 'casual',
        'courserepeat': '1'  # indefinite period
    }
    return render_template(
        "cadmin_add_course.html",
        course=course
    )


@app.route("/cadmin/add_course/save", methods=['POST', ])
@require_perm('sysadmin')
def cadmin_add_course_save():
    """ accept saved settings for a new course"""
    user_id = session['user_id']
    form = request.form
    if 'cancel_edit' in form:
        flash("Course creation cancelled")
        return redirect(url_for("setup_courses"))

    if not 'save_changes' in form:
        abort(400)

    if not 'name' in form:
        flash("You must give the course a name!")
        return redirect(url_for("cadmin_add_course"))

    if not 'title' in form:
        flash("You must give the course a title!")
        return redirect(url_for("cadmin_add_course"))

    name = form.get('name', '')
    title = form.get('title', '')
    coursetemplate = form.get('coursetemplate', 'casual')
    courserepeat = form.get('courserepeat', 'eternal')

    course = {
        'name': name,
        'title': title,
        'coursetemplate': coursetemplate,
        'courserepeat': courserepeat
    }

    if len(name) < 1:
        flash("You must give the course a name!")
        return render_template(
            "cadmin_add_course.html",
            course=course
        )

    existing = Course.get_by_name(name)
    if existing:
        flash("There is already a course called %(name)s" % existing)
        return render_template(
            "cadmin_add_course.html",
            course=course
        )
    if len(title) < 1:
        flash("You must give the course a title!")
        return render_template(
            "cadmin_add_course.html",
            course=course
        )

    course = Course.create(name, title, user_id, 1)
    if not course:
        flash("Error Adding Course!")
        return render_template(
            "cadmin_add_course.html",
            course=course
        )

    course.create_config(coursetemplate, int(courserepeat))

    flash("Course %s added!" % name)
    return redirect(url_for("cadmin_top", course_id=course.id))


@app.route("/cadmin/<int:course_id>/createexam")
@require_course_perm(("examcreate", "coursecoord", "courseadmin"))
def cadmin_create_exam(course_id):
    """ Provide a form to create/edit a new assessment """
    course = Course.get(course_id)
    if not course:
        abort(404)

    topics = CourseAdmin.get_create_exam_q_list(course_id)

    today = datetime.now()
    return render_template(
        "exam_edit.html",
        course=course,
        topics=topics,
        #  defaults
        exam={
            'id': 0,
            'start_date': int(date_from_py2js(today)+86400000),  # tomorrow
            'end_date': int(date_from_py2js(today)+90000000),  # tomorrow + hour
            'start_hour': int(today.hour),
            'end_hour': int(today.hour + 1),
            'start_minute': int(today.minute),
            'end_minute': int(today.minute),
            'duration': 60,
            'title': "Assessment",
            'archived': 1,
        }
    )


@app.route("/cadmin/<int:course_id>/exam_results/<int:exam_id>")
@require_course_perm(("examcreate", "coursecoord", "courseadmin"))
def cadmin_exam_results(course_id, exam_id):
    """ View the results of an assessment """
    course = Course.get(course_id)
    if not course:
        abort(404)

    exam = Exam.get(exam_id)
    if not exam:
        abort(404)

    if not exam.course == course_id:
        flash("Assessment %s does not belong to this course." % exam_id)
        return redirect(url_for('cadmin_top', course_id=course_id))

    exam.start_date = date_from_py2js(exam.start)
    exam.end_date = date_from_py2js(exam.end)
    exam.start_hour = exam.start.hour
    exam.end_hour = exam.end.hour
    exam.start_minute = exam.start.minute
    exam.end_minute = exam.end.minute

    groups = [Group.get(g_id)
              for g_id
              in Group.active_by_course(course_id)]
    results = {}
    uids = set([])
    totals = {}
    for group in groups:
        results[group.id] = exam.get_marks(group)
        for user_id in results[group.id]:
            uids.add(user_id)
            if not user_id in totals:
                totals[user_id] = 0.0
            for qt, val in results[group.id][user_id].iteritems():
                totals[user_id] += val['score']

    questions = exam.get_qts_list()
    users = {}
    for uid in uids:
        users[uid] = User.get(uid)
    return render_template(
        "cadmin_examresults.html",
        course=course,
        exam=exam,
        results=results,
        groups=groups,
        users=users,
        questions=questions,
        when=datetime.now().strftime("%H:%m, %a %d %b %Y"),
        totals=totals
    )


@app.route("/cadmin/<int:course_id>/exam/<int:exam_id>/<int:group_id>/export.csv")
@require_course_perm(("coursecoord", "courseadmin","viewmarks"))
def cadmin_export_csv(course_id, exam_id, group_id):
    """ Send the group results as a CSV file """
    course = Course.get(course_id)
    if not course:
        abort(404)

    exam = Exam.get(exam_id)
    if not exam:
        abort(404)

    if not exam.course == course_id:
        flash("Assessment %s does not belong to this course." % exam_id)
        return redirect(url_for('cadmin_top', course_id=course_id))

    group = Group.get(group_id)
    output = Spreadsheets.exam_results_as_spreadsheet(course_id, group, exam_id)
    response = make_response(output)
    response.headers.add('Content-Type', "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet; charset=utf-8")
    response.headers.add('Content-Disposition', 'attachment; filename="OASIS_%s_%s_Results.xlsx"' % (course.title, exam.title))

    return response


@app.route("/cadmin/<int:course_id>/exam/<int:exam_id>/view/<int:student_uid>")
@require_course_perm(("coursecoord", "courseadmin", "viewmarks"))
def cadmin_exam_viewmarked(course_id, exam_id, student_uid):
    """  Show a student's marked assessment results """

    course = Course.get(course_id)
    if not course:
        abort(404)
    exam = Exam.get(exam_id)
    if not exam:
        abort(404)
    results, examtotal = Assess.render_own_marked_exam(student_uid, exam_id)

    if examtotal is False:
        status = 0
    else:
        status = 1
    marktime = exam.get_mark_time(student_uid)
    firstview = exam.get_student_start_time(student_uid)
    submittime = exam.get_submit_time(student_uid)

    try:
        datemarked = Util.human_date(marktime)
    except AttributeError:
        datemarked = None
    try:
        datefirstview = Util.human_date(firstview)
    except AttributeError:
        datefirstview = None
    try:
        datesubmit = Util.human_date(submittime)
    except AttributeError:
        datesubmit = None

    user = User.get(student_uid)

    if submittime and firstview:
        taken = submittime-firstview
        takenmins = (taken.seconds/60)
    else:
        takenmins = None

    return render_template(
        "cadmin_markedresult.html",
        course=course,
        exam=exam,
        results=results,
        examtotal=examtotal,
        datesubmit=datesubmit,
        datemarked=datemarked,
        datefirstview=datefirstview,
        taken=takenmins,
        user=user,
        status=status
    )


@app.route("/cadmin/<int:course_id>/exam/<int:exam_id>/unsubmit/<int:student_uid>", methods=['POST', ])
@require_course_perm(("coursecoord", "courseadmin", "viewmarks", "altermarks"))
def cadmin_exam_unsubmit(course_id, exam_id, student_uid):
    """ "unsubmit" the student's assessment and reset their timer so they can
        log back on and have another attempt.
    """
    course = Course.get(course_id)
    try:
        exam = Exam.get(exam_id)
    except KeyError:
        exam = {}
        abort(404)
    exam.unsubmit(student_uid)
    user = User.get(student_uid)
    flash("""Assessment for %s unsubmitted and timer reset.""" % user.uname)
    return redirect(url_for("cadmin_exam_viewmarked",
                            course_id=course.id,
                            exam_id=exam['id'],
                            student_uid=student_uid))


@app.route("/cadmin/<int:course_id>/editexam/<int:exam_id>")
@require_course_perm(("examcreate", "coursecoord", "courseadmin"))
def cadmin_edit_exam(course_id, exam_id):
    """ Provide a form to edit an assessment """
    course = Course.get(course_id)
    if not course:
        abort(404)

    exam = Exam.get(exam_id)
    if not exam:
        abort(404)

    if not exam.course == course_id:
        flash("Assessment %s does not belong to this course." % int(exam_id))
        return redirect(url_for('cadmin_top', course_id=course_id))

    exam.start_date = date_from_py2js(exam.start)
    exam.end_date = date_from_py2js(exam.end)
    exam.start_hour = exam.start.hour
    exam.end_hour = exam.end.hour
    exam.start_minute = exam.start.minute
    exam.end_minute = exam.end.minute

    return render_template(
        "exam_edit.html",
        course=course,
        exam=exam
    )


@app.route("/cadmin/<int:course_id>/exam_edit_submit/<int:exam_id>",
           methods=["POST", ])
@require_course_perm(("examcreate", "coursecoord", "courseadmin"))
def cadmin_edit_exam_submit(course_id, exam_id):
    """ Provide a form to edit an assessment """
    user_id = session['user_id']

    course = Course.get(course_id)
    if not course:
        abort(404)

    if "exam_cancel" in request.form:
        flash("Assessment editing cancelled.")
        return redirect(url_for('cadmin_top', course_id=course_id))

    exam = CourseAdmin.exam_edit_submit(request, user_id, course_id, exam_id)
    db.session.add(exam)
    db.session.save()
    flash("Assessment saved.")
    return render_template(
        "exam_edit_submit.html",
        course=course,
        exam=exam
    )


@app.route("/cadmin/<int:course_id>/group/<int:group_id>/edit")
@require_course_perm(("useradmin", "coursecoord", "courseadmin"))
def cadmin_editgroup(course_id, group_id):
    """ Present a page for editing a group, membership, etc.
    """
    group = None
    try:
        group = Group.get(group_id)
    except KeyError:
        abort(404)

    if not group:
        abort(404)

    course = Course.get(course_id)
    if not course:
        abort(404)
    ulist = group.members()
    members = [User.get(uid) for uid in ulist]
    return render_template("courseadmin_editgroup.html",
                           course=course,
                           group=group,
                           members=members)


@app.route("/cadmin/<int:course_id>/editgroup/<int:group_id>/addperson",
           methods=["POST", ])
@require_course_perm(("useradmin", "coursecoord", "courseadmin"))
def cadmin_editgroup_addperson(course_id, group_id):
    """ Add a person to the group.
    """
    group = None
    try:
        group = Group.get(g_id=group_id)
    except KeyError:
        abort(404)

    if not group:
        abort(404)

    if not "uname" in request.form:
        abort(400)

    new_uname = request.form['uname']
    # TODO: Sanitize username
    try:
        new_user = User.get_by_uname(new_uname)
    except KeyError:
        flash("User '%s' Not Found" % new_uname)
    else:
        if not new_user.id:
            flash("User '%s' Not Found" % new_uname)
        elif new_user.id in group.members():
            flash("%s is already in the group." % new_uname)
        else:
            group.add_member(new_user.id)
            flash("Added %s to group." % (new_uname,))

    return redirect(url_for('cadmin_editgroup',
                            course_id=course_id,
                            group_id=group_id))


@app.route("/cadmin/<int:course_id>/groupmember/<int:group_id>",
           methods=["POST", ])
@require_course_perm(("useradmin", "coursecoord", "courseadmin"))
def cadmin_editgroup_member(course_id, group_id):
    """ Perform operation on group member. Remove/Edit/Etc
    """
    group = None
    try:
        group = Group.get(g_id=group_id)
    except KeyError:
        abort(404)

    if not group:
        abort(404)

    done = False
    cmds = request.form.keys()
    # expecting   "remove_UID"
    for cmd in cmds:
        if '_' in cmd:
            op, uid = cmd.split("_", 1)
            if op == "remove":
                uid = int(uid)
                user = User.get(uid)
                group.remove_member(uid)
                flash("%s removed from group" % user.uname)
                done = True

    if not done:
        flash("No actions?")
    return redirect(url_for('cadmin_editgroup',
                            course_id=course_id,
                            group_id=group_id))


@app.route("/cadmin/<int:course_id>/assign_coord", methods=["POST", ])
@require_course_perm(("courseadmin", "coursecoord"))
def cadmin_assign_coord(course_id):
    """ Set someone as course coordinator
"""
    course = Course.get(course_id)
    if not course:
        abort(404)

    if not "coord" in request.form:
        abort(400)

    new_uname = request.form['coord']
    # TODO: Sanitize username
    try:
        new_user = User.get_by_uname(new_uname)
    except KeyError:
        flash("User '%s' Not Found" % new_uname)
    else:
        if not new_user:
            flash("User '%s' Not Found" % new_uname)
        else:
            Permission.add_perm(new_user.id, course_id, 3)  # courseadmin
            Permission.add_perm(new_user.id, course_id, 4)  # coursecoord
            flash("%s can now control the course." % (new_uname,))

    return redirect(url_for('cadmin_config', course_id=course_id))


@app.route("/cadmin/<int:course_id>/remove_coord/<string:coordname>")
@require_course_perm(("courseadmin", "coursecoord"))
def cadmin_remove_coord(course_id, coordname):
    """ Remove someone as course coordinator
    """
    course = Course.get(course_id)
    if not course:
        abort(404)

    try:
        new_user = User.get_by_uname(coordname)
    except KeyError:
        flash("User '%s' Not Found" % coordname)
    else:
        if not new_user:
            flash("User '%s' Not Found" % coordname)
        else:
            Permission.delete_perm(new_user.id, course_id, 3)  # courseadmin
            Permission.delete_perm(new_user.id, course_id, 4)  # coursecoord
            flash("%s can no longer control the course." % (coordname,))

    return redirect(url_for('cadmin_config', course_id=course_id))


@app.route("/cadmin/<int:course_id>/topics", methods=['GET', 'POST'])
@require_course_perm(("questionedit", "courseadmin", "coursecoord"))
def cadmin_edittopics(course_id):
    """ Present a page to view and edit all topics, including hidden. """
    course = None
    try:
        course = Course.get(course_id)
    except KeyError:
        abort(404)

    if not course:
        abort(404)

    topics = course.topics()
    return render_template("courseadmin_edittopics.html",
                           course=course,
                           topics=topics)


@app.route("/cadmin/<int:course_id>/deactivate", methods=["POST", ])
@require_course_perm(("courseadmin", "coursecoord"))
def cadmin_deactivate(course_id):
    """ Mark the course as inactive
    """
    course = None
    try:
        course = Course.get(course_id)
    except KeyError:
        abort(404)

    if not course:
        abort(404)

    course.set_active(False)
    flash("Course %s marked as inactive" % (course.name,))
    return redirect(url_for("cadmin_config", course_id=course_id))


@app.route("/cadmin/<int:course_id>/group/<int:group_id>/detach_group", methods=["POST", ])
@require_course_perm(("useradmin", "courseadmin", "coursecoord"))
def cadmin_group_detach(course_id, group_id):
    """ Mark the course as inactive
    """
    course = None
    try:
        course = Course.get(course_id)
    except KeyError:
        abort(404)

    if not course:
        abort(404)

    group = Group.get(g_id=group_id)
    course.del_group(group_id)
    flash("Group %s removed from course" % (group.name,))
    return redirect(url_for("cadmin_config", course_id=course_id))


@app.route("/cadmin/<int:course_id>/activate", methods=["POST", ])
@require_course_perm(("courseadmin", 'coursecoord'))
def cadmin_activate(course_id):
    """ Mark the course as active
    """
    course = None
    try:
        course = Course.get(course_id)
    except KeyError:
        abort(404)

    if not course:
        abort(404)

    course.set_active(True)
    flash("Course %s marked as active" % (course.name,))
    return redirect(url_for("cadmin_config", course_id=course_id))


@app.route("/cadmin/<int:course_id>/topics_save", methods=['POST'])
@require_course_perm(("questionedit", "coursecoord", 'courseadmin'))
def cadmin_edittopics_save(course_id):
    """ Accept a submitted topics page and save it."""
    course = None
    try:
        course = Course.get(course_id)
    except KeyError:
        abort(404)

    if not course:
        abort(404)

    if "cancel" in request.form:
        flash("Changes Cancelled!")
        return redirect(url_for('cadmin_top', course_id=course_id))

    if CourseAdmin.do_topic_update(course, request):
        flash("Changes Saved!")
    else:
        flash("Error Saving!")
    return redirect(url_for('cadmin_edittopics', course_id=course_id))


@app.route("/cadmin/<int:course_id>/edittopic/<int:topic_id>")
@require_course_perm(("questionedit", 'coursecoord', 'courseadmin'))
def cadmin_edit_topic(course_id, topic_id):
    """ Present a page to view and edit a topic, including adding/editing
        questions and setting some parameters.
    """
    user_id = session['user_id']

    if not course_id:
        abort(404)

    course = Course.get(course_id)
    topic = Topic.get(topic_id)
    questions = [question
                 for question in topic.qtemplates()]
    for question in questions:
        question['embed_id'] = DB.get_qt_embedid(question['id'])
        if question['embed_id']:
            question['embed_url'] = "%s/embed/question/%s/question.html" % \
                                    (OaConfig.parentURL, question['embed_id'])
        else:
            question['embed_url'] = None
        question['editor'] = DB.get_qt_editor(question['id'])

    all_courses = Course.all()
    all_courses = [crse
                   for crse in all_courses
                   if Permission.satisfy_perms(user_id, int(crse.id),
                                   ("questionedit", "courseadmin",
                                    "sysadmin"))]
    all_courses.sort(lambda f, s: cmp(f['name'], s['name']))

    all_course_topics = []
    for course in all_courses:
        topics = course.topics()
        if topics:
            all_course_topics.append({'course': course.name, 'topics': topics})

    questions.sort(key=lambda k: k['position'])
    return render_template(
        "courseadmin_edittopic.html",
        course=course,
        topic=topic,
        questions=questions,
        all_course_topics=all_course_topics
    )


@app.route("/cadmin/<int:course_id>/topic/<int:topic_id>/<int:qt_id>/history")
@require_course_perm(("questionedit", 'coursecoord', 'courseadmin'))
def cadmin_view_qtemplate_history(course_id, topic_id, qt_id):
    """ Show the practice history of the question template. """
    if not course_id:
        abort(404)

    course = Course.get(course_id)
    topic = Topic.get(topic_id)
    qtemplate = DB.get_qtemplate(qt_id)
    year = datetime.now().year
    years = range(year, year-6, -1)

    return render_template(
        "courseadmin_viewqtemplate.html",
        course=course,
        topic=topic,
        qtemplate=qtemplate,
        years=years
    )


@app.route("/cadmin/<int:course_id>/topic/<int:topic_id>")
@require_course_perm(("questionedit", 'coursecoord', 'courseadmin'))
def cadmin_view_topic(course_id, topic_id):
    """ Present a page to view a topic, including basic stats """
    user_id = session['user_id']

    if not course_id:
        abort(404)

    course = Course.get(course_id)
    topic = Topic.get(topic_id)
    questions = [question for question in topic.qtemplates()]
    for question in questions:
        question['embed_id'] = DB.get_qt_embedid(question['id'])
        if question['embed_id']:
            question['embed_url'] = "%s/embed/question/%s/question.html" % \
                                    (OaConfig.parentURL, question['embed_id'])
        else:
            question['embed_url'] = None
        question['editor'] = DB.get_qt_editor(question['id'])

    all_courses = Course.all()
    all_courses = [course for course in all_courses
                   if Permission.satisfy_perms(user_id, course.id,
                                   ("questionedit", "courseadmin",
                                    "sysadmin"))]
    all_courses.sort(lambda f, s: cmp(f['name'], s['name']))

    all_course_topics = []
    for course in all_courses:
        topics = course.topics()
        if topics:
            all_course_topics.append({'course': course.name, 'topics': topics})

    questions.sort(key=lambda k: k['position'])
    return render_template(
        "courseadmin_viewtopic.html",
        course=course,
        topic=topic,
        questions=questions,
        all_course_topics=all_course_topics,
    )


@app.route("/cadmin/<int:course_id>/topic_save/<int:topic_id>",
           methods=['POST'])
@require_course_perm(("questionedit", 'coursecoord', 'courseadmin'))
def cadmin_topic_save(course_id, topic_id):
    """ Receive the page from cadmin_edit_topic and process any changes. """
    user_id = session['user_id']

    if not course_id:
        abort(404)

    if "cancel_edit" in request.form:
        flash("Topic Changes Cancelled!")
        return redirect(url_for('cadmin_top', course_id=course_id))

    if "save_changes" in request.form:
        (what, result) = Setup.doTopicPageCommands(request, topic_id, user_id)

        if what == 1:
            # flash(result['mesg'])
            return redirect(url_for('cadmin_edit_topic',
                                    course_id=course_id,
                                    topic_id=topic_id))
        if what == 2:
            return result

    flash("Error saving Topic Information!")
    log(ERROR, "Error saving Topic Information " % repr(request.form))
    return redirect(url_for('cadmin_edit_topic',
                            course_id=course_id,
                            topic_id=topic_id))


@app.route("/cadmin/<int:course_id>/perms")
@require_course_perm(("useradmin", 'coursecoord', 'courseadmin'))
def cadmin_permissions(course_id):
    """ Present a page for them to assign permissions to the course"""
    course = Course.get(course_id)

    permlist = Permission.get_course_perms(course_id)
    perms = {}
    for uid, pid in permlist:  # (uid, permission)
        if not uid in perms:
            user = User.get(uid)
            perms[uid] = {
                'uname': user.uname,
                'fullname': user.fullname,
                'pids': []
            }
        perms[uid]['pids'].append(pid)

    return render_template(
        "courseadmin_permissions.html",
        perms=perms,
        course=course,
        pids=[5, 10, 14, 11, 8, 9, 15, 2]
    )


@app.route("/cadmin/<int:course_id>/perms_save", methods=["POST", ])
@require_course_perm(("useradmin", 'coursecoord', 'courseadmin'))
def cadmin_permissions_save(course_id):
    """ Present a page for them to save new permissions to the course """
    user_id = session['user_id']

    if "cancel" in request.form:
        flash("Permission changes cancelled")
        return redirect(url_for("cadmin_top", course_id=course_id))

    CourseAdmin.save_perms(request, course_id, user_id)
    flash("Changes saved")
    return redirect(url_for("cadmin_permissions", course_id=course_id))


@app.route("/cadmin/<int:course_id>/add_group", methods=["POST", ])
@require_course_perm(("useradmin", 'coursecoord', 'courseadmin'))
def cadmin_course_add_group(course_id):
    """ We've been asked to add a group to the course.
    """
    course = Course.get(course_id)
    group_id = int(request.form.get("addgroup", "0"))
    if not group_id:
        flash("No group selected")
        return redirect(url_for('cadmin_config', course_id=course_id))

    course.add_group(group_id)
    group = Group.get(group_id)
    flash("Group %s added" % (group.name,))
    return redirect(url_for('cadmin_config', course_id=course_id))


@app.route("/cadmin/<int:course_id>/questions_import/<topic_id>", methods=['POST',])
@require_course_perm(("questioneditor", 'coursecoord', 'courseadmin'))
def cadmin_course_questions_import(course_id, topic_id):
    """ Take an OAQ file and import any questions in it into topic
    """

    if 'importfile' in request.files:
        data = request.files['importfile'].read()
    else:
        flash("No file uploaded?")
        return redirect(url_for("cadmin_edit_topic",
                                course_id=course_id,
                                topic_id=topic_id))

    if len(data) > 52000000:  # approx 50Mb
        flash("Upload is too large, 50MB Maximum.")
        return redirect(url_for("cadmin_edit_topic",
                                course_id=course_id,
                                topic_id=topic_id))

    num = External.import_qts_from_zip(topic_id, data)
    if num is False:
        flash("Invalid OASISQE file? No data recognized.")
        return redirect(url_for("cadmin_edit_topic",
                                course_id=course_id,
                                topic_id=topic_id))
    if num is 0:
        flash("Empty OASISQE file? No questions found.")
        return redirect(url_for("cadmin_edit_topic",
                                course_id=course_id,
                                topic_id=topic_id))

    flash("%s questions imported!" % num)
    return redirect(url_for("cadmin_edit_topic",
                            course_id=course_id,
                            topic_id=topic_id))

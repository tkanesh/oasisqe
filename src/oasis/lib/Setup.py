# -*- coding: utf-8 -*-

# This code is under the GNU Affero General Public License
# http://www.gnu.org/licenses/agpl-3.0.html

""" OaSetup.py
    Setup related stuff.
"""

from flask import flash
from logging import log, ERROR
from oasis.database import db_session
import StringIO
from oasis.lib import External
from oasis.models.Topic import Topic
from flask import send_file, abort
from oasis.models.QTemplate import QTemplate


def doTopicPageCommands(request, topic_id, user_id):
    """We've been asked to perform some operations on the Topic page.

        Expecting form fields:

            selected_QTID
            position_QTID
            name_QTID

        where QTID is a question template id. May receive many.

            new_position
            new_name
            new_type

            select_cmd = 'copy' | 'move'
            select_target = TOPICID of target topic

    """

    form = request.form
    mesg = []

    # Make a list of all the commands to run
    cmdlist = []
    for command in request.form.keys():
        (cmd, data) = command.split('_', 2)
        value = form[command]
        if not value == "none":
            cmdlist += [{'cmd': cmd, 'data': data, 'value': value}]

    # Now run them:
    # Titles first
    for command in [cmd for cmd in cmdlist if cmd['cmd'] == 'name']:
        qtid = int(command['data'])
        qt = QTemplate.get(qtid)
        title = command['value']
        qt.title = title
        db.session.add(qt)

    # Then positions
    for command in [cmd for cmd in cmdlist if cmd['cmd'] == 'position']:
        qtid = int(command['data'])
        try:
            position = int(command['value'])
        except ValueError:
            position = 0
        DB.update_qt_pos(qtid, topic_id, position)

    # Then commands on selected questions
    target_cmd = form.get('target_cmd', None)
    if target_cmd:
        qtids = [int(cmd['data']) for cmd in cmdlist if cmd['cmd'] == 'select']
        try:
            target_topic = Topic.get(int(form.get('target_topic', 0)))
        except ValueError:
            target_topic = None

        if target_cmd == 'move':
            if target_topic:
                for qtid in qtids:
                    qt = QTemplate.get(qtid)
                    topic = Topic.get(target_topic)
                    flash("Moving %s to %s" % (qt.title, topic.title))
                    DB.move_qt_to_topic(qtid, target_topic)
        if target_cmd == 'copy':
            if target_topic:
                for qtid in qtids:
                    qt = QTemplate.get(qtid)
                    topic = Topic.get(target_topic)
                    flash("Copying %s to %s" % (qt.title, topic.title))
                    newid = DB.copy_qt_all(qtid)
                    DB.add_qt_to_topic(newid, target_topic)

        if target_cmd == 'hide':
            for qtid in qtids:
                position = DB.get_qtemplate_topic_pos(qtid, topic_id)
                if position > 0:  # If visible, make it hidden
                    DB.update_qt_pos(qtid, topic_id, -position)
                    title = DB.get_qt_name(qtid)
                    flash("Made '%s' Hidden" % title)

        if target_cmd == 'show':
            for qtid in qtids:
                position = DB.get_qtemplate_topic_pos(qtid, topic_id)
                if position == 0:  # If hidden, make it visible
                    newpos = DB.get_qt_max_pos_in_topic(topic_id)
                    DB.update_qt_pos(qtid, topic_id, newpos + 1)
                    title = DB.get_qt_name(qtid)
                    flash("Made '%s' Visible" % title)
                if position < 0:  # If hidden, make it visible
                    DB.update_qt_pos(qtid, topic_id, -position)
                    title = DB.get_qt_name(qtid)
                    flash("Made '%s' Visible" % title)
        if target_cmd == "export":
            data = External.qts_to_zip(qtids, fname="oa_export", suffix="oaq")
            if not data:
                abort(401)

            sIO = StringIO.StringIO(data)
            return 2, send_file(sIO, "application/oasisqe", as_attachment=True, attachment_filename="oa_export.zip")

    # Then new questions
    new_title = form.get('new_title', None)
    if new_title:
        if not (new_title == "[New Question]" or new_title == ""):
            new_position = form.get('new_position', 0)
            try:
                new_position = int(new_position)
            except ValueError:
                new_position = 0
            new_qtype = form.get('new_qtype', 'raw')
            try:
                new_maxscore = float(form.get('new_maxscore', 0))
            except ValueError:
                new_maxscore = 0
            newid = DB.create_qt(user_id,
                                 new_title,
                                 "No Description",
                                 1,
                                 new_maxscore,
                                 0)
            if newid:
                mesg.append("Created new question, id %s" % newid)
                DB.update_qt_pos(newid,
                                 topic_id,
                                 new_position)
                DB.create_qt_att(newid,
                                 "qtemplate.html",
                                 "application/oasis-html",
                                 "empty",
                                 1)
                DB.create_qt_att(newid,
                                 "qtemplate.html",
                                 "application/oasis-html",
                                 "empty",
                                 1)
                if new_qtype == "oqe":
                    mesg.append("Creating new question, id %s as OQE" % newid)
                    DB.create_qt_att(newid,
                                     "_editor.oqe",
                                     "application/oasis-oqe",
                                     "",
                                     1)
                if new_qtype == "raw":
                    mesg.append("Creating new question, id %s as RAW (%s)" %
                                (newid, new_qtype))
                    DB.create_qt_att(newid,
                                     "datfile.txt",
                                     "application/oasis-dat",
                                     "0",
                                     1)
            else:
                mesg.append("Error creating new question, id %s" % newid)
                log(ERROR,
                    "Unable to create new question (%s) (%s)" %
                    (new_title, new_position))
    return 1, {'mesg': mesg}

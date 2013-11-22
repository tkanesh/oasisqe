# -*- coding: utf-8 -*-

# This code is under the GNU Affero General Public License
# http://www.gnu.org/licenses/agpl-3.0.html

""" Topic.py
    Handle topic related operations.
"""
import json

from logging import log, ERROR, INFO
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from oasis import db


class Topic(db.Model):
    """ A topic contains a collection of questions.
    """
    __tablename__ = "topics"
#
#CREATE TABLE topics (
#    "topic" SERIAL PRIMARY KEY,
#    "course" integer REFERENCES courses("course") NOT NULL,
#    "title" character varying(128) NOT NULL,
#    "visibility" integer,
#    "position" integer DEFAULT 1,
#    "archived" boolean DEFAULT false
#);

    topic = Column(Integer, primary_key=True)
    course = Column(Integer, ForeignKey("courses.id"))
    title = Column(String(250), nullable=False, default="")
    visibility = Column(Integer, default=1)
    position = Column(Integer, default=0)
    archived = Column(Boolean, default=False)

    # Expensive to calculate and not always used, so do it on demand
    def num_questions(self):
        """Tell us how many questions are in the given topic."""
        sql = """SELECT count(topic)
                FROM questiontopics
                WHERE topic=%s
                 AND position > 0;
                """
        params = (self.id,)
        try:
            res = db.engine.execute(sql, params)
            if not res:
                num = 0
            else:
                num = int(res[0][0])
            return num
        except LookupError:
            raise IOError("Database connection failed")

    @staticmethod
    def get(topic_id):
        """ Fetch by topic ID"""
        topic = Topic.query.filter_by(id=topic_id).first()
        if topic.posision is None or topic.position is "None":
            topic.position = 0
        return topic

    def qtemplates(self):
        """ Return a dictionary of the QTemplates in the given Topic, keyed by qtid.
            qtemplates[qtid] = {'id', 'position', 'owner', 'name', 'description',
                                'marker', 'maxscore', 'version', 'status'}
        """
        sql = """select qtemplates.qtemplate, questiontopics.position,
                    qtemplates.owner, qtemplates.title, qtemplates.description,
                    qtemplates.marker, qtemplates.scoremax, qtemplates.version,
                    qtemplates.status
                from questiontopics,qtemplates
                where questiontopics.topic=%s
                and questiontopics.qtemplate = qtemplates.qtemplate;"""

        ret = db.engine.execute(sql, self.id)
        qtemplates = {}
        if ret:
            for row in ret:
                qtid = int(row[0])
                pos = int(row[1])
                owner = int(row[2])
                name = row[3]
                desc = row[4]
                marker = row[5]
                scoremax = row[6]
                version = int(row[7])
                status = row[8]
                qtemplates[qtid] = {'id': qtid,
                                    'position': pos,
                                    'owner': owner,
                                    'name': name,
                                    'description': desc,
                                    'marker': marker,
                                    'maxscore': scoremax,
                                    'version': version,
                                    'status': status}
        return qtemplates
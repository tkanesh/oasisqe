# Test the model system


from unittest import TestCase
import os
from oasis.lib import Permissions

from oasis import app, db

from oasis.models.User import User
from oasis.models.Feed import Feed
from oasis.models.Course import Course
from oasis.models.Group import Group
from oasis.models.Message import Message
from oasis.models.Period import Period
from oasis.models.Topic import Topic
from oasis.models.UFeed import UFeed


class TestApp(TestCase):

    def setUp(self):

        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join('/tmp', 'test.db')
        app.config['TESTING'] = True
        self.app = app.test_client()
        db.create_all()

    def tearDown(self):

        db.drop_all()
        db.session.remove()

    def test_user_obj(self):

        u = User.create(
            uname="bob1",
            passwd='',
            givenname="Bob",
            familyname="Bobsson",
            acctstatus=2,
            student_id="123456",
            email="bob@example.com",
            expiry=None,
            source='feed',
            confirmation_code='',
            confirmed=True)

        self.assertEquals("bob1", u.uname)
        self.assertEquals("Bob Bobsson", u.fullname)
        self.assertTrue(u.confirmed)
        self.assertFalse(u.expiry)

        u.set_password("12345")
        self.assertTrue(u.verify_password("12345"))
        self.assertFalse(u.verify_password("123456"))
        self.assertFalse(u.verify_password(""))
        self.assertFalse(u.verify_password("1234567890"*100))
        self.assertFalse(u.verify_password("' or 1=1;"))

        u.set_password("1234")

        self.assertTrue(u.verify_password("1234"))
        self.assertFalse(u.verify_password("123456"))
        self.assertFalse(u.verify_password(""))
        self.assertFalse(u.verify_password("1234567890"*1024))
        self.assertFalse(u.verify_password("' or 1=1;"))

        passwd = u.gen_confirm_code()
        u.set_password(passwd)

        self.assertGreater(len(passwd), 5)
        self.assertTrue(u.verify_password(passwd))
        self.assertFalse(u.verify_password(""))

        u.set_password("Ab%^/")

        db.session.add(u)
        db.session.commit()

        u2 = User.get_by_uname("bob1")

        self.assertTrue(u2.verify_password("Ab%^/"))

    def test_create_course(self):

        c = Course.create("test1", "This is a test Course", 0, 4)

        self.assertEqual("test1", c.name)
        self.assertEqual(4, c.type)
        self.assertEqual(0, c.owner)
        self.assertEqual("This is a test Course", c.title)

    def test_user_permissions(self):

        u = User.create(
            uname="bob2",
            passwd='',
            givenname="Bob",
            familyname="Bobsson",
            acctstatus=2,
            student_id="123456",
            email="bob@example.com",
            expiry=None,
            source='feed',
            confirmation_code='',
            confirmed=True)

       # Permissions.add_perm(u.id, 0, 1)  # superuser

       # self.assertTrue(Permissions.check_perm(u.id, 0, 0))
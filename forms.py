from flask_wtf import FlaskForm as Form
from wtforms import StringField, PasswordField, SubmitField, BooleanField, TextAreaField
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError

from models import User

def email_exists(form, field):
    """email_exists validator"""
    if User.select().where(User.email == field.data).exists():
        raise ValidationError('Email already exists!')


def username_exists(form, field):
    """username_exists validator"""
    if User.select().where(User.username == field.data).exists():
        raise ValidationError("Username already exists!")


class LoginForm(Form):
    username = StringField('Username', validators=[DataRequired()])  # add a regex requirement
    password = PasswordField('Password', validators=[DataRequired(), Length(min=2)])
    submit = SubmitField('Login')


class RegisterForm(Form):
    username = StringField('Username', validators=[DataRequired(), username_exists])
    firstname = StringField('First Name')
    lastname = StringField('Last Name')
    email = StringField('Email', validators=[DataRequired(), Email(), email_exists])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=2),
                                                     EqualTo('password2', message='Password must match')])
    password2 = PasswordField('Confirm',)
    submit = SubmitField('Register')

class TalkForm(Form):
    notes = TextAreaField('Tell us your thoughts!')
    submit = SubmitField('Save')
    
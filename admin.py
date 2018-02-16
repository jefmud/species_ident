# admin.py
# modify this for additional administrative views

from flask import abort, g, render_template

# adding flask_admin
from flask_admin import Admin, AdminIndexView, expose
from flask_admin.contrib.peewee import ModelView

import models

# flask-admin setup
class MyAdminView(AdminIndexView):
    @expose('/')
    def index(self):
        try:
            if g.user.is_admin:
                return render_template('admin.html')
        except Exception as e:
            print(e)
            pass # silently fail for unauthorized trying to access admin space
        
        abort(403)

def initialize(app):     
    admin = Admin(app, template_mode='bootstrap3', index_view=MyAdminView())
    admin.add_view(ModelView(models.User))
    
    # ADD YOUR ADDITIONAL ADMIN VIEWS BELOW (use User model as a template)
    
    admin.add_view(ModelView(models.Species))
    admin.add_view(ModelView(models.Image))
    admin.add_view(ModelView(models.Observation))

    return admin
# app.py
# the main server app
import sys
import logging
from datetime import datetime  as dt

# server parameters
HOST = '0.0.0.0'
PORT = 5000
DEBUG = False

# basic flask imports
from flask import (abort, Flask, flash, g, get_flashed_messages, redirect, render_template, request, url_for)

# flask bootstrap
from flask_bootstrap import Bootstrap

# adding flask_login 
from flask_login import (LoginManager, UserMixin, login_user, login_required,
                         logout_user, current_user)

# local imports
import forms
import models
import admin

# my local utilities
from utils import get_object_or_404

app = Flask(__name__)
app.secret_key = 'PutYourSecretInHere'
# set up logging
file_handler = logging.FileHandler('app.log')
app.logger.addHandler(file_handler)
app.logger.setLevel(logging.INFO)
# set up admin
admin = admin.initialize(app)
# include bootstrap
Bootstrap(app)

# flask-login setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    """returns user user based on user_id or None"""
    try:
        return models.User.get(models.User.id == user_id)
    except models.DoesNotExist:
        return None

# request handlers
@app.before_request
def before_request():
    g.db = models.DATABASE
    try:
        g.db.connect()
    except Exception as e:
        app.log('ERROR: DB connect @ {}'.format(dt.now()))
        app.log('ERROR = {}'.format(e))
    g.user = current_user

@app.after_request
def after_request(response):
    try:
        g.db.close()
    except Exception as e:
        app.log('ERROR: attempt to close DB @'.format(dt.now()))
        app.log('ERROR = {}'.format(e))
    return response

# Regular routes

@app.route('/')
def index():
    """main landing page"""
    # todo, at some point, needs to become multi-project friendly
    user_stats = models.get_user_stats()
    data = {
        'observations': 0,
        'snapshots': models.IMAGE_COUNT,
        'percent': 0, 'leader':"", 'leader_count': 0
    }
    for username, user_observations in user_stats:
        # update leaderboard in data dict
        if user_observations > data['leader_count']:
            data['leader_count'] = user_observations
            data['leader'] = username
        # accumulate total observations    
        data['observations'] += user_observations
        
    # I removed the snapshot query to save time, administrator needs to update when more images
    # are added to the database (celery task?)
    # data['snapshots'] = len(images)
    try:
        # trap error just in case.
        data['percent'] = data['observations']/float(data['snapshots']) * 100
    except:
        data['percent'] = 0.0
    
    top_limit = len(user_stats)
    if top_limit > 10:
        top_limit = 10
    return render_template('index.html', data=data, user_stats=user_stats[:top_limit])


@app.route('/login', methods=['GET', 'POST'])
def login():
    """show login screen, handle data"""
    if current_user.is_authenticated:
        flash('Please logout first.')
        return redirect(url_for('profile'))
    form = forms.LoginForm()
    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data
        try:
            user = models.User.get(models.User.username==username)
            if user.authenticate(password):
                login_user(user)
                flash('Welcome {}!'.format(user.username), category='success')
                app.logger.info('user login by {} @ {}'.format(user.username, dt.now()))
                return redirect(url_for('profile'))
        except Exception as e:
            print(e)

        flash('Incorrect login information', category='danger')
        app.logger.warning('login failed for {} @ {}'.format(username, dt.now()))

    return render_template('login/login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    """logout the user"""
    app.logger.info('username {} logout @ {}'.format(g.user, dt.now()))
    logout_user()
    flash("You have been logged out.", category="warning")
    
    return redirect(url_for('index'))

@app.route('/register', methods=['GET','POST'])
def register():
    """view to register a new user"""
    # todo mail user with confirmation link
    # anti-robot validation
    if current_user.is_authenticated:
        flash('Please logout before registering a new email', category='warning')
        return redirect(url_for('index'))

    form = forms.RegisterForm()
    if form.validate_on_submit():
        try:
            models.User.create_user(
                username=form.username.data,
                email=form.email.data,
                password=form.password.data,
                firstname=form.firstname.data,
                lastname=form.lastname.data,
                is_admin=False
            )
        except:
            flash("Problems registering this user = {}".format(form.email.data),
                  category='danger')
            app.logger.error('problems registering user {} @ {}'.format(form.email.data, dt.now()))
        else:
            flash("Thanks for registering as {}".format(form.email.data), category="info")
            app.logger.info('registered new user = {} @ {}'.format(form.email.data, dt.now()))
            return redirect(url_for('index'))

    return render_template('login/register.html', form=form)

@app.route('/profile')
def profile():
    return redirect('/')

@app.route('/profile')
@login_required
def profile_original():
    """profile shows summary data for current user"""
    # get all talk
    talk = models.Talk.select().where(
        models.Talk.user == g.user._get_current_object(),
        )
    # get all species
    species_dict = models.species_dict()
    species_master = {}
    for species_name, species_data in species_dict.items():
        # get observations on the particular species for current user
        obs = models.Observation.select().where(
            models.Observation.user == g.user._get_current_object(),
            models.Observation.species == species_data.get('id')
        )
        # update a "personalized" species_master dictionary, which is sent out for rendering in the template
        species_data.update({'count':len(obs)})
        species_master.update({species_name:species_data})
        
        # get last 5 observations
        all_obs = models.Observation.select().where(models.Observation.user == g.user._get_current_object())
        obs_limit = 10
        if len(all_obs) < obs_limit:
            obs_limit = len(obs)
            
    return render_template('profile.html', species_master=species_master, obs=all_obs[:obs_limit], talk=talk)

@app.route('/profile/<int:species_id>')
@login_required
def profile_species(species_id):
    """Show a listing of observations of a particular species by the user"""
    species = get_object_or_404(models.Species, species_id)
    obs = models.Observation.select().where(models.Observation.user==g.user._get_current_object(),
                                            models.Observation.species==species_id)
    
    # todo decorate this with species info from SnapShot Serengeti
    return render_template('observe_species.html', obs=obs, species=species)

@app.route('/observe_view/<int:obs_id>')
@login_required
def observe_view(obs_id):
    """show an individual observation"""
    obs = get_object_or_404(models.Observation, obs_id)
    # todo, we should actually render a page here!
    return str(obs)
    
@app.route('/_user_audit')
@login_required
def _user_audit():
    if current_user.is_admin:
        models.audit_users()
        flash("User audit completed",category="success")
        return redirect(url_for('admin.index'))
    app.logger.error('unauthorized attempt at user_audit by {} @ {}'.format(g.user,dt.now()))
    abort(403) # they should not have run this give 'em the 403
    
@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/image/<int:image_id>')
def show_image(image_id):
    try:
        image = models.Image.get(models.Image.id==image_id)
    except:
        return "No image with that id"
    return render_template('image.html', image=image)

@app.route('/species/<name>')
def species(name):
    try:
        s = models.Species.get(models.Species.name==name)
    except:
        return "not found"
    test = request.args['p']
    if s.isa(test) == True:
        msg = '{} is a {}'.format(s,test)
    elif s.isa(test) == False:
        msg = '{} is NOT a {}'.format(s,test)
    else:
        msg = '{} does not have a property {}'.format(s,test)
    return msg
    

@app.route('/selection', methods=('GET', 'POST'))
def selection():
    """test of rendering a selection matrix"""
    species = models.Species.select()
    if request.method == 'POST':
        s = request.form['species']
        count = request.form['count']
        # print(s,count)
    return render_template('selection.html', species=species) 
    
@app.route('/_observe/save/<int:image_id>/<int:count>/<species>/<int:next_id>')
@login_required
def _observe_save(image_id, count, species, next_id=0):
    """saves an observation and moves to next_id"""
    try:
        # if species id is numeric, use it
        species_id = int(species)
    except:
        try:
            # lookup the species id
            species = models.Species.get(models.Species.name == species)
            species_id = species.id
        except:
            flash("No species with that name or id", category="danger")
            app.logger.warning('failed looking up species "{}"'.format(species))
            return redirect(url_for('observe',image_id=image_id))
    
    try:
        # save the observation
        models.Observation.create(
            user=g.user._get_current_object(),
            image=image_id,
            count=count,
            species=species_id
        )
        # move on to next_id (if zero, it is a random image)
        return redirect(url_for('observe', image_id=next_id))
    except Exception as e:
        flash("Problems saving observation", category="danger")
        app.logger.error('problems saving observation for user={} image_id={}, count={}, species_id={}'.format(g.user,image_id,count,species_id))
        app.logger.error(e)
        return redirect(url_for('observe',image_id=image_id))
        
        
        
@app.route('/observe')
@app.route('/observe/<int:image_id>', methods=('GET','POST'))
@login_required
def observe(image_id=0):
    if image_id == 0:
        # observe something that has never been classified before
        unclassified_image = models.get_unclassified_image(image_id)
        return redirect(url_for('observe',image_id=unclassified_image.id))
        
    # get image or show a 404
    image = get_object_or_404(models.Image,image_id)
    species = models.Species.select() # get the species table.
    
    talkform = forms.TalkForm()
    
    if request.method == 'POST':
        # handle talk first
        if talkform.validate_on_submit():
            try:
                models.Talk.create(
                    user=g.user._get_current_object(),
                    image=image.id,
                    notes=talkform.notes.data
                    )
                return redirect(url_for('observe', image_id=image.id))
            except:
                flash("Problems creating snapshot notes", category="danger")
                app.logger.error('problems creating note for user={}, image={}'.format(g.user,image_id))
                
            return redirect(url_for('observe', image_id=image.id))
        
        name = request.form.get('species', None)
        if name is None:
            return redirect(url_for('observe', image_id=image.id))
        
        count = request.form.get('count', 0)
        try:
            count = int(count)
        except:
            count = 0
        
        species_dictionary = models.species_dict(species)
        user_identified_species_id = species_dictionary[name].get('id')

        # save the observation
        try:
            models.Observation.create(
                user=g.user._get_current_object(),
                image=image.id,
                species=user_identified_species_id,
                count=count
            )
            # flash('Observation saved-- species="{}"'.format(name), category='success')
            return redirect(url_for('observe', image_id=image.id))
        except Exception as e:
            print(e)
            flash('Problems saving observation!', category='danger')
            app.logger.error('problems saving observation user={}, image={}, count={}, species={}'.format(g.user,image_id,count,user_identified_species_id))
            
    # get any observations made by the user on the current image
    obs = models.Observation.select().where(
        models.Observation.user == g.user._get_current_object(), 
        models.Observation.image == image
    )
    talk = models.Talk.select().where(
        models.Talk.user == g.user._get_current_object(),
        models.Talk.image == image
    )
    
    return render_template('observe.html', image=image, species=species, obs=obs, talk=talk, talkform=talkform)

@app.route('/show/<int:image_id>')
def image_show(image_id):
    image = get_object_or_404(models.Image,image_id)
    return render_template('image.html', image=image)

@app.route('/talk/delete/<int:item_id>')
@login_required
def talk_delete(item_id):
    talk = get_object_or_404(models.Talk, item_id)
    if talk.user == g.user._get_current_object() or g.user.is_admin:
        image_id = talk.image.id
        talk.delete_instance()
        return redirect(url_for('observe', image_id=image_id))
    app.logger.warning('failed delete of talk item user={} talk={}'.format(g.user,item_id))
    abort(403) # the user is not allowed to delete this talk item

@app.route('/observe/delete/<int:item_id>')
@login_required
def observe_delete(item_id):
    observation = get_object_or_404(models.Observation, item_id)
    if observation.user == g.user._get_current_object() or g.user.is_admin:
        image_id = observation.image.id
        observation.delete_instance()
        return redirect(url_for('observe', image_id=image_id))
    app.logger.warning('failed delete of observation user={}, observation={}'.format(g.user, item_id))
    abort(403) # the user is not allowed to delete this observation
        
if __name__ == '__main__':
    args = sys.argv
    # override args if needed below
    # args.append('--runserver')
    if '--createsuperuser' in args:
        models.create_superuser()
        app.logger.info('creating admin user initiated')
        print("** superuser created **")
    elif '--updateimages' in args:
        models.update_images(args)
        print("** image update complete **")
        sys.exit(0)
    elif '--initdatabase' in args:
        app.logger.info('database initialize begin')
        models.initialize_database()
        app.logger.info('database initialize completed')
        print("** database initialized **")
    elif '--host' in args:
        PORT = args[args.index('--host') + 1]
    elif '--port' in args:
        PORT = int(args[args.index('--port') + 1])
    elif '--runserver' in args:
        # see settings at the top of the file
        app.logger.info('app started host={}, port={}'.format(HOST,PORT))
        app.run(host=HOST, port=PORT, debug=DEBUG)
    elif '--paste' in args:
        from paste import httpserver
        app.logger.info('app started host={}, port={}'.format(HOST,PORT))
        httpserver.serve(app, host=HOST, port=PORT)
    else:
        msg = """
        app.py valid command line options
        --host (default = '0.0.0.0', defines visibility '0.0.0.0' is completely open)
        --port (default = 5000, defines which port server will run on)
        --createsuperuser (allows creation of an administrative user)
        --initdatabase (initializes the database if required)
        --runserver (runs the server on port configured in source code)
        --paste (runs a paste wsgi server on port configured in source code)
        """
        print(msg)

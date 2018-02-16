# python imports
import datetime
import json
import os
from random import randint
import sys


# flask bcrypt for passwords
from flask_bcrypt import generate_password_hash, check_password_hash

# basic peewee import style
from peewee import *
# from playhouse.hybrid import hybrid_property

# magic from flask_login
from flask_login import UserMixin

DATABASE = SqliteDatabase('app.db')

IMAGE_COUNT = 30122

# model definitions
class BaseModel(Model):
    class Meta:
        database = DATABASE


class User(UserMixin, BaseModel):
    """User is the user entity model"""
    username = CharField(unique=True)
    email = CharField(unique=True)
    password = CharField()
    firstname = CharField()
    lastname = CharField()
    is_admin = BooleanField(default=False)
    joined_at = DateTimeField(default=datetime.datetime.now)

    @classmethod
    def create_user(cls, username, email, password, firstname='', lastname='', is_admin=False):
        hashed_password = generate_password_hash(password)
        try:
            with DATABASE.transaction():
                cls.create(username=username, firstname=firstname, lastname=lastname, email=email,
                           password=hashed_password, is_admin=is_admin)
        except IntegrityError:
            raise ValueError('username or email already exists')
        
    def authenticate(self, password):
        if check_password_hash(self.password, password):
            return True
        return False

    def reset_password(self, password):
        self.password = generate_password_hash(password)
        self.save()

    def __repr__(self):
        return self.username
    
    def observations(self):
        """return number of observations made for leaderboard"""
        obs = Observation.select().where(Observation.user==self)
        return len(obs)
    
    class Meta:
        order_by = ('-username',)
    
class Species(BaseModel):
    """species model includes a name, ref_url and data"""
    name = CharField(unique=True)
    # ref_url is used to prompt a user on possible page with species details
    ref_url = CharField(max_length=100, default='')
    # data is a pseudo-JSON element
    data = TextField(default='')
    
    def __dict__(self):
        return json.loads(self.data)
    
    def isa(self, prop):
        """species.isa('carnivore') = True or False (None of no property set)"""
        return self.__dict__().get(prop, None)
        
    def __repr__(self):
        return self.name

def initialize_database():
    """drop tables and init images with caution, this takes a LONG time"""
    DATABASE.connect()
    # try: DATABASE.drop_table(Species)
    # except: pass
    # try: DATABASE.drop_table(Image)
    # except: pass
    DATABASE.create_tables([User,Species, Image, Observation, Talk], safe=True)
    #species_init()
    # image_init()


def audit_users():
    """audits user table for unencrypted passwords, and fixes them"""
    users = User.select()
    for user in users:
        try:
            user.authenticate(user.password)
        except:
            user.reset_password(user.password)
            
def create_superuser():
    """console method to create an admin/superuser"""
    # not if using python3, change raw_input and print statements!
    # if you're reading this code, you already understand this.
    print ("Enter data for admin/superuser (all fields required)")
    if '2.7' in sys.version:
        username = raw_input("Enter username: ")
        email = raw_input("Enter email: ")
        password = raw_input("Enter password: ")
    else:
        username = input("Enter username: ")
        email = input("Enter email: ")
        password = input("Enter password: ")    
        
    try:
        User.create_user(username=username, email=email, password=password, is_admin=True)
    except Exception as e:
        print (e)
        print ("database probably needs to be created, please use --initdatabase command line switch")
        

    
def species_init():
    """initialize Species model with fixture data, JSON from SavanaHorizon included"""
    fname = "data/species_table.ser"
    with open(fname,"r") as fp:
        data = json.loads(fp.read())
    for item in data:
        print item
        fields = item.get('fields')
        try:
            s = Species.get(Species.name==fields.get('name'))
        except:
            s = Species.create(name=fields.get('name'), ref_url=fields.get('ref_url'),
                               data=json.dumps(fields))
            s.save()
            print "saving {}".format(s.name)

class Image(BaseModel):
    """Image model references a remote image base_url joined to filepath"""
    # todo, pull exif metadata return via a method
    base_url = CharField()
    filepath = CharField(unique=True)
    site = CharField()
    timestamp = DateTimeField(default=datetime.datetime.now)
    
    def url(self):
        return os.path.join(self.base_url, self.filepath)
    
    def __repr__(self):
        return self.filepath
    
    
def image_init():
    """initialize the image database table from the fixture file"""
    # warning, this is a big file and will take more than an hour!
    fname = "data/image_files.txt"
    base_url = "http://media.itg.wfu.edu/sites/"
    count = 0
    with open(fname,"r") as fp:
        data = fp.read()
        
    lines = data.split() # break into individual lines
    
    for line in lines:
        if '.JPG' in line.upper():
            # remove leading relative path './'
            if line[:2] == './':
                line = line[2:]
            # path = os.path.join(base_url,line)
            try:
                # see if image is already in database
                image = Image.get(Image.filepath==filepath)
                print("{} already in database".format(image))
            except:
                # instantiate an Image object and save to database
                image = Image.create(filepath=line, base_url=base_url, site='')
                try:
                    image.save()
                except Exception as e:
                    # whoops, something is f-ed up, maybe will recover?
                    print(e)
                del(image)
                count += 1
                if count % 1000 == 0:
                    print count
                
    
    
class Observation(BaseModel):
    """The observation model"""
    image = ForeignKeyField(Image, related_name="image")
    user = ForeignKeyField(User, related_name="user")
    species = ForeignKeyField(Species, related_name="species")
    count = IntegerField(default=1)
    notes = TextField(default='')
    _overlay = TextField(default='') # experimental JSON object
    timestamp = DateTimeField(default=datetime.datetime.now)
    
    @property
    def overlay(self):
        return json.loads(self.overlay)
    
    @overlay.setter
    def overlay(self, value):
        self._overlay = json.dumps(value)
    
    def __repr__(self):
        return "{}={} {} @ {}".format(self.species, self.count, self.user, self.timestamp)
    
    class Meta:
        order_by = ('-timestamp','user')
    
class Talk(BaseModel):
    """Talk - a table for a note made about an image, goal for this to be searchable"""
    image = ForeignKeyField(Image, related_name="talkimage")
    user = ForeignKeyField(User, related_name="talkuser")
    notes = TextField(default='')
    timestamp = DateTimeField(default=datetime.datetime.now)
    
    class Meta:
        order_by = ('-timestamp','user')
    
def get_unclassified_image(suggestion=None):
    """returns an image object that is unclassified"""
    # may not be the smartest way to do this, but will make it better later
    
    # start at a random picture
    seed = randint(1,IMAGE_COUNT)
    while seed:
        try:
            image = Image.get(Image.id==seed)
            obs = Observation.select().where(Observation.image==image)
            if len(obs) == 0:
                # no observations, so we can return it
                return image
        except:
            pass
        seed += 1
        if seed > IMAGE_COUNT:
            # wrap around
            seed = 1
        
def species_dict(species=None):
    """produce a nice master dictionary representation of all the species"""
    master = {}
    if species is None:
        # species called without an existing list, fill the list
        species = Species.select()
    for s in species:
        item = s.__dict__()
        item.update({'id':s.id})
        master.update({s.name: item})
    return master
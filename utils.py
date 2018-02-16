from flask import abort
def get_object_or_404(cls, object_id):
    """get an object by its id or abort(404) - inspired by Django"""
    try:
        obj = cls.get(cls.id==object_id)
        return obj
    except:
        abort(404)
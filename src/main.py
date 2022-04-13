import os
import json
import subprocess
import urllib.parse as urllib

from flask import Flask
from flask import request
from flask import redirect
from flask import make_response
from flask import render_template


from flask_restful import Api
from flask_restful import Resource


import codectrl
import colouredlogs


# local imports
import api


app_regular = Flask(__name__)
app_restful = Api(app_regular)


BASE_URL = '/'
app_regular.config['UPLOAD_FOLDER'] = "/tmp"
app_regular.config['MAX_CONTENT_PATH'] = 1000000


class Index(Resource):
    """ / """
    @staticmethod
    def get():
        """ If cookies are invalid then redirect to login """
        if api.check_cookie(request.cookies.get('auth')):
            res = make_response(redirect(f'{BASE_URL}control-panel'))
        else:
            res = make_response(redirect(f'{BASE_URL}login/?error=not+logged+in"'))

        return res


class Login(Resource):
    """ /login """
    @staticmethod
    def get():
        """ Show the login screen to the user """
        res = make_response(render_template("login.html"))
        res.status_code = 200
        return res


    @staticmethod
    def post():
        """ Check password and assign random cookie """
        cookie, status =  api.login_if_correct(request)

        if status != 200:
            res = make_response(redirect(f'{BASE_URL}login/?error={urllib.quote_plus(cookie)}'))
            res.content_type = "text/html"
            return res

        res = make_response(redirect(f'{BASE_URL}'))
        res.set_cookie("auth", cookie)
        return res


class ControlPanel(Resource):
    """ /control-panel """
    @staticmethod
    def get():
        """ Show the main control panel page """
        if not api.check_cookie(request.cookies.get('auth')):
            return make_response(redirect(f'{BASE_URL}login/?error=not+logged+in"'))

        # should probably do some formatting in the future
        res = make_response(render_template('controlpanel.html', bots=os.listdir('../bots/')))
        res.status_code = 200
        return res


class UploadNewBot(Resource):
    """ /control-panel/new """
    @staticmethod
    def get():
        """ Show the bot creation page """
        if not api.check_cookie(request.cookies.get('auth')):
            return make_response(redirect(f'{BASE_URL}login/?error=not+logged+in"'))

        res = make_response(render_template("addnew.html"))
        res.status_code = 200
        return res

    @staticmethod
    def post():
        """ Create a new bot """
        if not api.check_cookie(request.cookies.get('auth')):
            return make_response(redirect(f'{BASE_URL}login/?error=not+logged+in"'))

        response, status = api.upload_bot(request)
        if status != 200:
            return make_response(redirect(f'{BASE_URL}control-panel/new/?error={urllib.quote_plus(response)}"'))

        return make_response(redirect(f'{BASE_URL}control-panel"'))


class BotController(Resource):
    """ /control-panel/<botname> """
    @staticmethod
    def get(botname):
        """ Show information about a bot"""
        if not api.check_cookie(request.cookies.get('auth')):
            return make_response(redirect(f'{BASE_URL}login/?error=not+logged+in"'))

        # should probably do some formatting in the future
        # TODO: sanitise the shit out of this, and only let it run if its actually an existing bot
        # TODO2: add things like the file structure
        res = make_response(subprocess.check_output(['podman', 'inspect', botname]))
        res.content_type = "application/json"
        res.status_code = 200
        return res

    @staticmethod
    def post(botname):
        """ Build and run a bot """
        if not api.check_cookie(request.cookies.get('auth')):
            return make_response(redirect(f'{BASE_URL}login/?error=not+logged+in"'))


        return api.build_start_bot(botname)






app_restful.add_resource(Index,
            f'{BASE_URL}')
app_restful.add_resource(Login,
            f'{BASE_URL}login',
            f'{BASE_URL}login/')
app_restful.add_resource(ControlPanel,
            f'{BASE_URL}control-panel',
            f'{BASE_URL}control-panel/')
app_restful.add_resource(UploadNewBot,
            f'{BASE_URL}control-panel/new',
            f'{BASE_URL}control-panel/new/')
app_restful.add_resource(BotController,
            f'{BASE_URL}control-panel/<botname>',
            f'{BASE_URL}control-panel/<botname>/')



if __name__ == "__main__":
    colouredlogs.install(milliseconds=True)
    app_regular.run(host="0.0.0.0", port=5000, debug=True)

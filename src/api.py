import os
import json
import string 
import subprocess

# Using a global to store cookies
# This way all cookies will reset when the app restarts.
VALID_COOKIES: list[dict[str, str]] = []


#local
# As the passwords are assigned by the sysadmin
# we can just store them in this file called secrets
import security
from secret import user_creds


# ================================================ Auth related stuff ==========================================


def gen_cookie(username: str) -> str:
    """ Generate and store a cookie """
    cookie = security.gen_uuid()

    VALID_COOKIES.append({"username": username, "cookie": cookie})

    # need to store the user information in the cookie data too
    return f"{username}|{cookie}"


def check_cookie(cookie_token) -> bool:
    """ Check if a username-cookie pair exists in the VALID_COOKIES array """

    # Invalid or non-existing cookie
    if not isinstance(cookie_token, str) or '|' not in cookie_token:
        return False

    # cookies are structured as `username|cookie`
    username, cookie = cookie_token.split('|')
    
    for token in VALID_COOKIES:
        if username == token['username'] and cookie == token['cookie']:
            return True

    return False


def login_if_correct(request) -> tuple[str, int]:
    """ check cookie and assign random cookie """
    username: str = request.form.get("username")
    password: str = request.form.get("password")


    if username is None:
        return "No username supplied", 400

    if password is None:
        return "No password supplied", 400

    for char in username:
        if char not in string.ascii_letters + string.digits + "_-.@":
            return f"Illegal character '{char}' in username", 400


    for user in user_creds:
        if user['username'] == username:
            if security.check_password(password, user['password']):
                return gen_cookie(username), 200
            else:
                break


    return "Username or password does not match any in the database", 403



# ================================================ Bot related stuff ==========================================


def upload_bot(request) -> tuple[str, int]:
    """ Check if all data is valid, and create a new bot """
    zipfile = request.files.get('file')
    bot_name: str = request.form.get('name')
    dockerfile: str = request.form.get('Dockerfile')

    if len(bot_name) < 2:
        return "Bot name must be at least 3 characters", 400

    if len(dockerfile) < 10:
        return "Invalid dockerfile: Unreasonably short", 400


    # make sure bot name is safe
    for char in bot_name:
        if char not in string.ascii_letters + string.digits + "_-":
            return f"Cannot include '{char}' in bot name", 400

    if ".." in bot_name:
        return "Cannot include '..' in bot name", 400



    # make sure zipfile name is safe
    # (if it exists)
    if zipfile is not None:
        # IMPORTANT: this can be fooled. Not sure if there is any scope to it,
        # but if there is then we should change this to a better check.
        if not zipfile.filename[-4:] == ".zip" or zipfile.content_type != 'application/zip':
            return "Uploaded file has to be a zipfile", 400


    if os.path.exists(f"../bots/{bot_name}"):
        return "A bot by this name already exists", 400


    # Its better to tell the user why it failed
    try:
        os.mkdir(f'../bots/{bot_name}')
        os.mkdir(f'../bots/{bot_name}/storage')

        with open(f"../bots/{bot_name}/Dockerfile", "w", encoding="utf-8") as outfile:
            outfile.write(dockerfile)

        if zipfile is not None:
            zipfile.save(f"../bots/{bot_name}/bot.zip")

    except Exception as err: # pylint: disable=broad-except
        return f"Internal server error while saving the bot: {err}", 500


    return "OK", 200


def update_bot(request, bot_name: str) -> tuple[str, int]:
    """
        Update the dockerfile and (if changed) the
        zip file associated with the bot
    """
    zipfile = request.files.get('file')
    dockerfile: str = request.form.get('Dockerfile')

    for char in bot_name:
        if char not in string.ascii_letters + string.digits + "-_":
            return f"Invalid character in bot name: '{char}'", 400

    if len(bot_name) < 2:
        return "Bot name must be at least 3 characters", 400


    if len(dockerfile) < 10:
        return "Invalid dockerfile: Unreasonably short", 400


    # bot has to already exist to run
    if not os.path.isdir(f"../bots/{bot_name}"):
        return "The requested bot does not exist, or has a different name!", 400


    with open(f"../bots/{bot_name}/Dockerfile", "w+", encoding='utf-8')as outfile:
        outfile.write(dockerfile)


    print('zipfile: ',zipfile.filename , type(zipfile))
    if zipfile is not None and len(zipfile.filename) > 3:
        zipfile.save(f"../bots/{bot_name}/bot.zip")

    return "OK", 200


def build_start_bot(bot_name: str) -> tuple[str, int]:
    """ Build and start a bot """

    for char in bot_name:
        if char not in string.ascii_letters + string.digits + "-_":
            return f"Invalid character in bot name: '{char}'", 400

    if len(bot_name) < 2:
        return "Bot name must be at least 3 characters", 400


    # bot has to already exist to run
    if not os.path.isdir(f"../bots/{bot_name}"):
        return "The requested bot does not exist, or has a different name!", 400

    if not os.path.isfile(f"../bots/{bot_name}/Dockerfile"):
        return "The requested bot has not been corrupted: missing dockerfile", 400



    # Get information about the bot.
    # This command will crash if the bot doesn't
    # exist yet, otherwise return json
    try:
        bot_info = json.loads(subprocess.check_output(['podman', 'inspect', bot_name]))
    except subprocess.CalledProcessError:
        bot_info = None


    # If the bot exists
    # Sometimes instead of none you get some random json that I didn't bother checking out
    if bot_info is not None and bot_info[0].get('State'):

        # Cannot run the bot twice
        if bot_info[0].get('State').get('Status') == "running":
            return "Bot is already running", 400

        # If the bot exists, but is not running then remove it
        if os.system(f"podman rm {bot_name}\
                > ../bots/{bot_name}/rm_logs\
                2>> ../bots/{bot_name}/rm_logs") != 0:
            return "An error occurred while deleting the old bot.\
                    Check the logfile for more information", 500


    # Try build the bot
    if os.system(f"cd ../bots/{bot_name} &&\
                  podman build -t {bot_name} .\
                  > build_logs\
                  2>> build_logs") != 0:
        return "An error occurred while building the bot.\
                Check the logfile for more information", 500


    # Try run the bot
    if os.system(f"cd ../bots/{bot_name} &&\
                  podman run --name {bot_name} -v $PWD/storage/:/app/storage -d {bot_name}\
                  > run_logs\
                  2>> run_logs") != 0:
        return "An error occurred while trying to run the bot.\
                Check the logfile for more information.", 500


    return "OK", 200


def kill_bot(bot_name: str) -> tuple[str, int]:
    """ Use the podman kill command to kill a bot """

    for char in bot_name:
        if char not in string.ascii_letters + string.digits + "-_":
            return f"Invalid character in bot name: '{char}'", 400

    if len(bot_name) < 2:
        return "Bot name must be at least 3 characters", 400

    # Make sure the bot exists
    if not os.path.isdir(f"../bots/{bot_name}"):
        return "The requested bot does not exist, or has a different name!", 404


    # Get information about the bot.
    # This command will crash if the bot doesn't
    # exist yet, otherwise return json
    try:
        bot_info = json.loads(subprocess.check_output(['podman', 'inspect', bot_name]))
    except subprocess.CalledProcessError:
        bot_info = None



    # If the bot exists
    # Sometimes instead of none you get some random json that I didn't bother checking out
    if bot_info is None or bot_info[0].get('State') is None:
        return "The requested bot does not exist, or has a different name!", 404


    # If the bot is running, then kill it before it can be deleted.
    if bot_info[0].get('State').get('Status') == "running":
        if os.system(f"podman kill {bot_name}\
                > ../bots/{bot_name}/kill_logs\
                2>> ../bots/{bot_name}/kill_logs") != 0:
            return "An error occurred while trying to kill the bot.\
                    Check the logfile for more information", 500


    return "Killed", 200


def get_bot_info(bot_name: str) -> tuple[dict, int]:
    """ Get information about a bot """

    # Going to a system command so has to be sanitized very well
    for char in bot_name:
        if char not in string.ascii_letters + string.digits + "-_":
            return {'error': "Invalid character in bot name: '{char}'"}, 400

    if len(bot_name) < 2:
        return {'error': "Bot name must be at least 3 characters"}, 400

    # Make sure the bot exists
    if not os.path.isdir(f"../bots/{bot_name}"):
        return {"error":"The requested bot does not exist, or has a different name!"}, 404


    # Use podman inspect to get data about the bot
    try:
        data: dict = json.loads(subprocess.check_output(['podman', 'inspect', bot_name]))[0]
    except subprocess.CalledProcessError:
        return {'error': "An error occurred while getting information about the bot"}, 500


    # Get data from logfiles
    logs = {}

    # get build logs
    if os.path.isfile(f'../bots/{bot_name}/build_logs'):
        with open(f'../bots/{bot_name}/build_logs', 'r', encoding='utf-8')as infile:
            logs['build'] = infile.read()

    # get run logs
    if os.path.isfile(f'../bots/{bot_name}/run_logs'):
        with open(f'../bots/{bot_name}/run_logs', 'r', encoding='utf-8')as infile:
            logs['run'] = infile.read()

    # get kill logs
    if os.path.isfile(f'../bots/{bot_name}/rm_logs'):
        with open(f'../bots/{bot_name}/rm_logs', 'r', encoding='utf-8')as infile:
            logs['rm'] = infile.read()

    # get remove logs
    if os.path.isfile(f'../bots/{bot_name}/kill_logs'):
        with open(f'../bots/{bot_name}/kill_logs', 'r', encoding='utf-8')as infile:
            logs['kill'] = infile.read()

    data['logs'] = logs



    # get filesystem tree for the bot directory
    try:
        # Split the tree output by newlines, remove the first line
        # and put it back together again.
        # This is needed as the first line of tree is the filename.
        # (If you find a way to do this with the tree command, let me know! :))
        data['tree'] = b'\n'.join( subprocess.check_output(
                        ['tree', f'../bots/{bot_name}/']
                        ).split(b'\n')[1:]).decode('utf-8')

    except subprocess.CalledProcessError:
        return {'error': "An error occurred while getting information about the bot"}, 500



    # If there is no state variable, then set it and return Un-built
    state =  data.get("State")
    if state is None:
        # Adding name as its needed for the UI and not present in
        # `data` at this point.
        data['Name'] = bot_name
        data['State'] = {'Status': "Un-built"}
        return data, 200


    return data, 200


def get_dockerfile(bot_name: str) -> tuple[str, int]:
    """ Return the contents of a dockerfile for a bot (if it exists) """

    # Going to a system command so has to be sanitized very well
    for char in bot_name:
        if char not in string.ascii_letters + string.digits + "-_":
            return "Invalid character in bot name: '{char}'", 400

    if len(bot_name) < 2:
        return "Bot name must be at least 3 characters", 400

    # Make sure the bot exists
    if not os.path.isdir(f"../bots/{bot_name}"):
        return "The requested bot does not exist, or has a different name!", 404


    if not os.path.isfile(f"../bots/{bot_name}/Dockerfile"):
        return "Corrupted bot directory: no dockerfile", 400


    # read the dockerfile and return it
    with open(f"../bots/{bot_name}/Dockerfile", "r", encoding="utf-8")as infile:
        data = infile.read()

    return data, 200

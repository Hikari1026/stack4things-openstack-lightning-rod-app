# Copyright 2017 MDSLAB - University of Messina
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

__author__ = "Nicola Peditto <n.peditto@gmail.com>"


#from iotronic_lightningrod.common.pam import pamAuthentication
from iotronic_lightningrod.common.auth import user_authentication
from iotronic_lightningrod.common import utils
from iotronic_lightningrod.lightningrod import board
from iotronic_lightningrod.lightningrod import iotronic_status
from iotronic_lightningrod.modules import device_manager
from iotronic_lightningrod.modules import Module
# from iotronic_lightningrod.modules import service_manager
from iotronic_lightningrod.modules import utils as lr_utils


from datetime import datetime
from flask import Flask
from flask import redirect
from flask import render_template
from flask import request
from flask import send_file
from flask import session as f_session
from flask import url_for
from flask import abort
# from flask import Response

import os
# import subprocess
import threading
import json
import zipfile

from oslo_config import cfg
from oslo_log import log as logging
LOG = logging.getLogger(__name__)

CONF = cfg.CONF


class RestManager(Module.Module):

    def __init__(self, board, session=None):
        super(RestManager, self).__init__("RestManager", board)
        self._data_folder = os.environ.get('DATA_FOLDER', '')

    def finalize(self):
        # Check if rest manager is already running
        isRestRunning = False
        thread_name = "rest_server"
        for t in threading.enumerate():
            if t.name == thread_name:
                isRestRunning = True
        
        if not isRestRunning:
            threading.Thread(target=self._runRestServer, args=(), name=thread_name).start()

    def restore(self):
        pass

    def _runRestServer(self):

        APP_PATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        TEMPLATE_PATH = os.path.join(APP_PATH, 'modules/web/templates/')
        STATIC_PATH = os.path.join(APP_PATH, 'modules/web/static/')
        AUTH_FILE = os.path.join(self._data_folder, 'auth.json')

        app = Flask(
            __name__,
            template_folder=TEMPLATE_PATH,
            static_folder=STATIC_PATH,
            static_url_path="/static"
        )

        app.secret_key = os.urandom(24).hex()  # to use flask session

        UPLOAD_FOLDER = os.path.join(self._data_folder, 'tmp')
        ALLOWED_EXTENSIONS = set(['zip'])
        ALLOWED_STTINGS_EXTENSIONS = set(['json'])
        app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

        @app.route('/')
        def home():

            if 'username' in f_session:
                return render_template('home.html')
            else:
                return render_template('login.html')

        def redirect_dest(fallback):
            dest = request.args.get('next')

            try:
                dest_url = url_for(dest)
            except Exception:
                return redirect(fallback)

            return redirect(dest_url)

        @app.route('/login', methods=['GET', 'POST'])
        def login():
            error = None

            if request.method == 'POST':

                if user_authentication(
                        AUTH_FILE,
                        str(request.form['username']),
                        str(request.form['password'])
                ):
                    f_session['username'] = request.form['username']
                    return redirect_dest(fallback="/")
                else:
                    error = 'Invalid Credentials. Please try again.'

            if 'username' in f_session:
                return render_template('home.html')
            else:
                return render_template('login.html', error=error)

        @app.route('/logout')
        def logout():
            # remove the username from the session if it's there
            f_session.pop('username', None)

            return redirect("/login", code=302)

        @app.route('/info')
        def info():
            wstun_status = 1 #service_manager.wstun_status()
            if wstun_status == 0:
                wstun_status = "Online"
            else:
                wstun_status = "Offline"

            service_list = "" #service_manager.services_list("list")
            if service_list == "":
                service_list = "no services exposed!"

            lr_cty = "N/A"
            from iotronic_lightningrod.lightningrod import wport
            sock_bundle = lr_utils.get_socket_info(wport)

            if sock_bundle != "N/A":
                lr_cty = sock_bundle[2] + " - " + sock_bundle[0] \
                    + " - " + sock_bundle[1]

            webservice_list = []

            # TODO nginx is not currently supported
            # nginx_path = "/etc/nginx/conf.d/"

            # if os.path.exists(nginx_path):
            #     active_webservice_list = [f for f in os.listdir(nginx_path)
            #                     if os.path.isfile(os.path.join(nginx_path, f))]

            #     if len(active_webservice_list) != 0:
            #         for ws in active_webservice_list:
            #             ws = ws.replace('.conf', '')
            #             webservice_list.append(ws)

            info = {
                'board_id': board.uuid,
                'board_name': board.name,
                'wagent': board.agent,
                'session_id': board.session_id,
                'timestamp': str(
                    datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%f')),
                'wstun_status': wstun_status,
                'board_reg_status': str(CONF.board_status),
                'iotronic_status': str(iotronic_status(CONF.board_status)),
                'service_list': service_list,
                'webservice_list': webservice_list,
                'serial_dev': str('Not supported'),#device_manager.getSerialDevice(),
                'nic': lr_cty,
                'lr_version': str(
                    utils.get_version("iotronic-lightningrod")
                )
            }

            return info, 200

        @app.route('/status')
        def status():

            try:

                if ('username' in f_session):

                    f_session['status'] = str(CONF.board_status)

                    wstun_status = 1 #service_manager.wstun_status()
                    if wstun_status == 0:
                        wstun_status = "Online"
                    else:
                        wstun_status = "Offline"

                    service_list = "" #service_manager.services_list("html")
                    if service_list == "":
                        service_list = "no services exposed!"

                    webservice_list = ""
                    nginx_path = "/etc/nginx/conf.d/"

                    # if os.path.exists(nginx_path):
                    #     active_webservice_list = [
                    #         f for f in os.listdir(nginx_path)
                    #             if os.path.isfile(os.path.join(nginx_path, f))
                    #     ]

                    #     for ws in active_webservice_list:
                    #         ws = ws.replace('.conf', '')[3:]
                    #         webservice_list = webservice_list + "\
                    #             <li>" + ws + "</li>"
                    # else:
                    #     webservice_list = "no webservices exposed!"

                    # if webservice_list == "":
                    #     webservice_list = "no webservices exposed!"
                    webservice_list = "no webservices exposed!"

                    lr_cty = "N/A"
                    from iotronic_lightningrod.lightningrod import wport
                    sock_bundle = lr_utils.get_socket_info(wport)

                    if sock_bundle != "N/A":
                        lr_cty = sock_bundle[2] + " - " + sock_bundle[0] \
                            + " - " + sock_bundle[1]

                    info = {
                        'board_id': board.uuid,
                        'board_name': board.name,
                        'wagent': board.agent,
                        'session_id': board.session_id,
                        'timestamp': str(
                            datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%f')),
                        'wstun_status': wstun_status,
                        'board_reg_status': str(CONF.board_status),
                        'iotronic_status': str(iotronic_status(CONF.board_status)),
                        'service_list': str(service_list),
                        'webservice_list': str(webservice_list),
                        'serial_dev': str('None'),#device_manager.getSerialDevice(),
                        'nic': lr_cty,
                        'lr_version': str(
                            utils.get_version("iotronic-lightningrod")
                        )
                    }

                    return render_template('status.html', **info)

                else:
                    return redirect(url_for('login', next=request.endpoint))

            except Exception as err:
                LOG.error(err)
                info = {
                        'messages': [str(err)]
                    }
                return render_template('status.html', **info)

        @app.route('/system')
        def system():
            if 'username' in f_session:
                info = {
                    'board_status': CONF.board_status
                }
                return render_template('system.html', **info)
            else:
                return redirect(url_for('login', next=request.endpoint))

        @app.route('/network')
        def network():
            if 'username' in f_session:
                info = {
                    'ifconfig': str('Not supported'),#device_manager.getIfconfig()
                }
                return render_template('network.html', **info)
            else:
                return redirect(url_for('login', next=request.endpoint))

        def lr_config(ragent, code):
            data = {
                'iotronic' : {
                    'board' : {
                        'code' : code
                    },
                    'wamp' : {
                        'registration-agent' : {
                            'url' : ragent,
                            'realm' : 's4t'
                        }
                    }
                }
            }
            with open(os.path.join(self._data_folder, 'iotronic', 'settings.json'), 'w') as f:
                json.dump(data, f, indent=2)

        def change_hostname(hostname):
            # TODO: not sure how to approach this

            """
            if hostname != "":
                bashCommand = "hostname %s " % (hostname)
                process = subprocess.Popen(bashCommand.split(),
                                           stdout=subprocess.PIPE)
                output, error = process.communicate()
            else:
                print("- No hostname specified!")
            """
            return

        def lr_install():
            replace_list = ['plugins', 'services', 'settings']
            templates_folder = os.path.join(self._data_folder, 'templates')
            iotronic_folder = os.path.join(self._data_folder, 'iotronic')

            for filename in replace_list:
                with open(os.path.join(templates_folder, f'{filename}.example.json'), 'r') as s:
                    with open(os.path.join(iotronic_folder, f'{filename}.json'), 'w') as d:
                        json.dump(json.load(s), d, indent=2)
            return

        def identity_backup():
            def create_zip(source_folder, output_zip):
                with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for root, _, files in os.walk(source_folder):
                        for file in files:
                            file_path = os.path.join(root, file)
                            zip_path = os.path.relpath(file_path, source_folder)
                            zipf.write(file_path, zip_path)

            source_fld = os.path.join(self._data_folder, 'iotronic')
            output_zip = os.path.join(self._data_folder, 'tmp', 'backup.zip')
            create_zip(source_fld, output_zip)
            return output_zip

        def identity_restore(filepath):

            def extract_zip(zip_file_path, extract_path):
                try:
                    with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
                        zip_ref.extractall(extract_path)
                        return extract_path
                except zipfile.BadZipFile:
                    print('Error: Invalid ZIP file')
                    return None
                except FileNotFoundError:
                    print('Error: File not found')
                    return None

            folder_name = datetime.now().strftime('backup_%Y_%m_%d_%H_%M_%S')
            ex_path = extract_zip(filepath, os.path.join(self._data_folder, 'tmp', folder_name))

            if ex_path == None:
                print("Error restoring backup")
                return "FAIL"
            
            replace_list = ['plugins', 'services', 'settings']

            for filename in replace_list:
                try:
                    with open(os.path.join(ex_path, f'{filename}.json'), 'r') as s:
                        with open(os.path.join(self._data_folder, 'iotronic', f'{filename}.json'), 'w') as d:
                            json.dump(json.load(s), d, indent=2)
                except FileNotFoundError:
                    print(f"Error restoring {filename}.json")
                except json.JSONDecodeError:
                    print(f"Error restoring {filename}.json")

            lr_utils.copy_folder(os.path.join(ex_path, 'plugins'), os.path.join(self._data_folder, 'iotronic', 'plugins'))

            return("OK")

        def allowed_file(filename):
            return '.' in filename and \
                   filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

        def allowed_settings(filename):
            return '.' in filename and \
                   filename.rsplit('.', 1)[1].lower() \
                   in ALLOWED_STTINGS_EXTENSIONS

        @app.route('/restore', methods=['GET', 'POST'])
        def upload_file():

            if ('username' in f_session) or str(CONF.board_status) == "first_boot":

                f_session['status'] = str(CONF.board_status)

                if request.form.get('dev_rst_btn') == 'Device restore':

                    if 'rst_file' not in request.files:

                        error = 'Identity restore result: No file uploaded!'
                        print(" - " + error)
                        info = {
                            'board_status': CONF.board_status
                        }
                        return render_template(
                            'config.html',
                            **info,
                            error=error
                        )

                    else:

                        file = request.files['rst_file']

                        if file.filename == '':

                            error = 'Identity restore result: No filename!'
                            print(" - " + error)
                            info = {
                                'board_status': CONF.board_status
                            }
                            return render_template('config.html', **info,
                                                   error=error)

                        else:
                            filename = file.filename
                            print("Identity file uploaded: " + str(filename))

                            if file and allowed_file(file.filename):
                                bpath = os.path.join(
                                    app.config['UPLOAD_FOLDER'],
                                    filename
                                )

                                bpath = bpath.replace(" ", "")
                                bpath = bpath.replace("(", "-")
                                bpath = bpath.replace(")", "-")

                                print("--> storage path: " + str(bpath))
                                file.save(bpath)

                                out_res = identity_restore(bpath)
                                print("--> restore result: " + str(out_res))
                                # restart LR
                                print("--> LR restarting in 5 seconds...")
                                f_session['status'] = "restarting"
                                lr_utils.LR_restart_delayed(5)

                                return redirect("/", code=302)

                            else:
                                error = 'Identity restore result: ' \
                                        + 'file extention not allowed!'
                                print(" - " + error)
                                info = {
                                    'board_status': CONF.board_status
                                }
                                return render_template(
                                    'config.html',
                                    **info,
                                    error=error
                                )
                                # return redirect("/config", code=302)

                else:
                    return redirect("/", code=302)
            else:
                return redirect(url_for('login', next=request.endpoint))

        @app.route('/backup', methods=['GET'])
        def backup_download():

            # LOG.info(request.query_string)
            # LOG.info(request.__dict__)

            if 'username' in f_session:

                print("Identity file downloading: ")

                filename = identity_backup()
                print("--> backup created:" + str(filename))

                path = str(filename)
                if path is None:
                    print("Error path None")
                try:
                    print("--> backup file sent.")
                    return send_file(path, as_attachment=True)
                except Exception as e:
                    print(e)
            else:
                return redirect(url_for('login', next=request.endpoint))

        @app.route('/factory', methods=['GET'])
        def factory_reset():
            if 'username' in f_session:

                print("Lightning-rod factory reset: ")

                f_session['status'] = str(CONF.board_status)

                # TODO: handle this

                # delete nginx conf.d files
                # os.system("rm /etc/nginx/conf.d/lr_*")
                # print("--> NGINX settings deleted.")

                # delete letsencrypt
                # os.system("rm -r /etc/letsencrypt/*")
                # print("--> LetsEncrypt settings deleted.")

                # delete var-iotronic
                # os.system("rm -r /var/lib/iotronic/*")
                # print("--> Iotronic data deleted.")

                # delete etc-iotronic
                # upd: lr_install now takes care of removal as well

                # exec lr_install

                # delete all files in iotronic folder
                iotronic_folder = os.path.join(self._data_folder, 'iotronic')
                lr_utils.delete_directory(iotronic_folder)
                os.makedirs(iotronic_folder)

                lr_install()
                print("--> Iotronic settings deleted.")
                # restart LR
                print("--> LR restarting in 5 seconds...")
                f_session['status'] = "restarting"

                lr_utils.LR_restart_delayed(5)

                return redirect("/", code=302)
            else:
                return redirect(url_for('login', next=request.endpoint))

        @app.route('/config', methods=['GET', 'POST'])
        def config():

            if ('username' in f_session) or str(CONF.board_status) == "first_boot":

                f_session['status'] = str(CONF.board_status)

                if request.method == 'POST':

                    req_body = request.get_json(silent=True)

                    LOG.debug(req_body)

                    if req_body != None:

                        if 'action' in req_body:

                            if req_body['action'] == "configure":
                                LOG.info("API LR configuration")

                                ragent = req_body['urlwagent']
                                code = req_body['code']

                                lr_config(ragent, code)

                                if 'hostname' in req_body:
                                    if req_body['hostname'] != "":
                                        change_hostname(req_body['hostname'])

                                return {"result": "LR configured, \
                                    authenticating..."}, 200

                        else:
                            abort(400)

                    elif request.form.get('reg_btn') == 'CONFIGURE':
                        ragent = request.form['urlwagent']
                        code = request.form['code']
                        lr_config(ragent, code)

                        hostname = request.form['hostname']
                        change_hostname(hostname)

                        return redirect("/status", code=302)

                    elif request.form.get('rst_btn') == 'RESTORE':
                        utils.restoreConf()
                        print("Restored")
                        f_session['status'] = "restarting"
                        return redirect("/", code=302)

                    elif request.form.get('fct_btn'):
                        utils.restoreFactoryConf()
                        print("Refactored")
                        print("--> LR restarting in 5 seconds...")
                        f_session['status'] = "restarting"
                        lr_utils.LR_restart_delayed(5)
                        return redirect("/", code=302)

                    elif request.form.get('change_hostname'):
                        hostname = request.form['hostname']
                        change_hostname(hostname)
                        return redirect("/system", code=302)

                    elif request.form.get('rst_settings_btn'):

                        print("Settings restoring from uploaded backup...")

                        if len(request.files) != 0:

                            if 'rst_settings_file' in request.files:

                                file = request.files['rst_settings_file']

                                if file.filename == '':

                                    error = 'Settings restore result: ' \
                                            + 'No filename!'
                                    print(" - " + error)
                                    info = {
                                        'board_status': CONF.board_status
                                    }
                                    return render_template(
                                        'config.html',
                                        **info,
                                        error=error
                                    )

                                else:

                                    filename = file.filename
                                    print(" - file uploaded: " + str(filename))

                                    if file and allowed_settings(filename):
                                        bpath = os.path.join(
                                            app.config['UPLOAD_FOLDER'],
                                            filename
                                        )
                                        file.save(bpath)

                                        try:
                                            os.system(
                                                'cp '
                                                + bpath
                                                + ' /etc/iotronic/'
                                                + 'settings.json'
                                            )
                                        except Exception as e:
                                            LOG.warning(
                                                "Error restoring " +
                                                "configuration " + str(e))

                                        print(" - done!")

                                        if CONF.board_status == "first_boot":
                                            # start LR
                                            print(" - LR starting "
                                                  + "in 5 seconds...")
                                            f_session['status'] = "starting"

                                        else:
                                            # restart LR
                                            print(" - LR restarting "
                                                  + "in 5 seconds...")
                                            f_session['status'] = "restarting"
                                            lr_utils.LR_restart_delayed(5)

                                        return redirect("/", code=302)

                                    else:
                                        error = 'Wrong file extention: ' \
                                                + str(filename)
                                        print(" - " + error)
                                        info = {
                                            'board_status': CONF.board_status
                                        }
                                        return render_template(
                                            'config.html',
                                            **info,
                                            error=error
                                        )

                            else:
                                error = 'input form error!'
                                print(" - " + error)
                                info = {
                                    'board_status': CONF.board_status
                                }
                                return render_template('config.html', **info,
                                                       error=error)

                        else:
                            error = "no settings file specified!"
                            print(" - " + error)
                            info = {
                                'board_status': CONF.board_status
                            }
                            return render_template(
                                'config.html',
                                **info,
                                error=error
                            )

                        return redirect("/config", code=302)

                    else:
                        print("Error POST request")
                        return redirect("/status", code=302)

                else:

                    if CONF.board_status == "first_boot":

                        urlwagent = request.args.get('urlwagent') or ""
                        code = request.args.get('code') or ""
                        info = {
                            'urlwagent': urlwagent,
                            'code': code,
                            'board_status': CONF.board_status
                        }

                        return render_template('config.html', **info)

                    else:

                        if request.args.get('bkp_btn'):
                            # utils.backupConf()
                            print("Settings file downloading: ")
                            path = "/etc/iotronic/settings.json"
                            if path is None:
                                print("Error path None")
                                return redirect("/config", code=500)

                            try:
                                fn_download = "settings_" + str(
                                    datetime.now().strftime(
                                        '%Y-%m-%dT%H:%M:%S.%f')) + ".json"
                                print("--> backup settings file sent.")
                                return send_file(
                                    path,
                                    as_attachment=True,
                                    attachment_filename=fn_download
                                )

                            except Exception as e:
                                print(e)
                                return redirect("/config", code=500)

                        elif request.args.get('rst_btn'):
                            utils.restoreConf()
                            print("Restored")
                            return redirect("/config", code=302)

                        elif request.args.get('fct_btn'):
                            utils.restoreFactoryConf()
                            print("Refactored")
                            print("--> LR restarting in 5 seconds...")
                            f_session['status'] = "restarting"
                            lr_utils.LR_restart_delayed(5)
                            return redirect("/", code=302)

                        elif request.args.get('lr_restart_btn'):
                            print("LR restarting in 5 seconds...")
                            f_session['status'] = "restarting"
                            lr_utils.LR_restart_delayed(5)
                            return redirect("/", code=302)

                        else:

                            info = {
                                'board_status': CONF.board_status
                            }
                            return render_template('config.html', **info)

            else:
                if request.method == 'POST':
                    req_body = request.get_json()

                    if req_body != None and str(CONF.board_status) != "first_boot":
                        return {"result": "LR already configured!"}, 403

                return redirect(url_for('login', next=request.endpoint))

        app.run(host='0.0.0.0', port=1474, debug=False, use_reloader=False)

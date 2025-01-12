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

from datetime import datetime
import json
import os

from oslo_config import cfg
from oslo_log import log as logging
LOG = logging.getLogger(__name__)

CONF = cfg.CONF

# global FIRST_BOOT
FIRST_BOOT = False

status_option = cfg.StrOpt(
    'board_status',
    default = 'None',
    help='Board status option'
)

CONF.register_opt(status_option)

class Board(object):

    def __init__(self):
        self.iotronic_config = {}

        self.board_config = {}
        self.name = None
        self.type = None
        self.status = None
        self.uuid = None
        self.code = None
        self.agent = None
        self.mobile = None
        self.session = None
        self.session_id = None
        self.agent_url = None

        self.location = {}

        self.device = None
        self.proxy = None

        self.wamp_config = None
        self.extra = {}

        self._data_folder = os.environ.get('DATA_FOLDER', '')
        self._settings = os.path.join(self._data_folder, 'iotronic', 'settings.json')

        self.loadSettings()

    def status_update(self, value):
        # Rest server may not restart so the board status must be changed dynamically
        # the board instance may be outdated so changing parameters must be updated using cfg
        self.status = value
        CONF.board_status = value

    def loadConf(self):
        """This method loads the JSON configuraton file: settings.json.

        :return:

        """

        try:

            with open(self._settings) as settings:
                lr_settings = json.load(settings)

        except Exception as err:
            LOG.error("Parsing error in " + self._settings + ": " + str(err))
            lr_settings = None

        return lr_settings

    def loadSettings(self):
        '''This method gets and sets the board attributes from the conf file.

        '''

        # Load all settings.json file
        self.iotronic_config = self.loadConf()

        try:
            # STATUS OPERATIVE
            board_config = self.iotronic_config['iotronic']['board']
            self.uuid = board_config['uuid']
            self.code = board_config['code']
            self.name = board_config['name']
            # self.status = board_config['status']
            self.status_update(board_config['status'])
            self.type = board_config['type']
            self.mobile = board_config['mobile']
            self.extra = board_config['extra']
            self.agent = board_config['agent']
            self.created_at = board_config['created_at']
            self.updated_at = board_config['updated_at']  # self.getTimestamp()
            self.location = board_config['location']

            self.extra = self.iotronic_config['iotronic']['extra']

            LOG.info('Board settings:')
            LOG.info(' - code: ' + str(self.code))
            LOG.info(' - uuid: ' + str(self.uuid))
            # LOG.debug(" - conf:\n" + json.dumps(board_config, indent=4))

            self.getWampAgent(self.iotronic_config)

        except Exception as err:
            if str(err) != 'uuid':
                if self.status == None:
                    LOG.warning("settings.json file exception: " + str(err))

            try:
                self.code = board_config['code']

                if self.code == "<REGISTRATION-TOKEN>":
                    # LR start to waiting for first configuration
                    global FIRST_BOOT
                    if FIRST_BOOT == False:
                        FIRST_BOOT = True
                        LOG.info("FIRST BOOT procedure started")
                        # self.status = "first_boot"
                        self.status_update('first_boot')
                else:
                    # self.status = None  # change to pre-registration 
                    self.status_update(None)
                    LOG.info('First registration board settings: ')
                    LOG.info(' - code: ' + str(self.code))
                    self.getWampAgent(self.iotronic_config)

            except Exception as err:
                LOG.error("Wrong code: " + str(err))
                # self.status = "first_boot"
                self.status_update('first_boot')
                # os._exit(1)

    def getWampAgent(self, config):
        '''This method gets and sets the WAMP Board attributes from the conf file.

        '''
        try:

            self.wamp_config = config['iotronic']['wamp']['main-agent']
            LOG.info('WAMP Agent settings:')

        except Exception:
            if (self.status is None) | (self.status == "registered") | \
                    (self.status == "first_boot"):
                self.wamp_config = \
                    config['iotronic']['wamp']['registration-agent']
                LOG.info('Registration Agent settings:')
            else:
                LOG.error(
                    "WAMP Agent configuration is wrong... "
                    "please check settings.json WAMP configuration... Bye!"
                )
                # os._exit(1)
                # self.status = "first_boot"
                self.status_update('first_boot')

        # self.agent_url = str(self.wamp_config['url'])
        LOG.info(' - agent: ' + str(self.agent))
        LOG.info(' - url: ' + str(self.wamp_config['url']))
        LOG.info(' - realm: ' + str(self.wamp_config['realm']))
        # LOG.debug("- conf:\n" + json.dumps(self.wamp_config, indent=4))

    def setConf(self, conf):
        # LOG.info("\nNEW CONFIGURATION:\n" + str(json.dumps(conf, indent=4)))

        with open(self._settings, 'w') as f:
            json.dump(conf, f, indent=4)

        # Reload configuration
        self.loadSettings()

    def updateStatus(self, status):
        self.iotronic_config['iotronic']['board']["status"] = status

        with open(self._settings, 'w') as f:
            json.dump(self.iotronic_config, f, indent=4)

    def getTimestamp(self):
        # datetime.now(tzlocal()).isoformat()
        return datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%f')

    def setUpdateTime(self):
        self.iotronic_config['iotronic']['board']["updated_at"] = \
            self.updated_at

        with open(self._settings, 'w') as f:
            json.dump(self.iotronic_config, f, indent=4)

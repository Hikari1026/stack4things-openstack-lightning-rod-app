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

# This is intended as a substitute for pam authentication as it is cumbersome to
# implement it in an app

import json

def user_authentication(creds_file, username, password, encoding='utf-8'):
    # USE HASH ASAP FFS
    with open(creds_file, 'r') as f:
        creds = json.load(f)
    return username == creds['username'] and password == creds['password']
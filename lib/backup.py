#
# Licensed to the Apache Software Foundation (ASF) under one or more
# contributor license agreements.  See the NOTICE file distributed with
# this work for additional information regarding copyright ownership.
# The ASF licenses this file to You under the Apache License, Version 2.0
# (the "License"); you may not use this file except in compliance with
# the License.  You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
from __future__ import print_function
from sys import stdin, stdout, stderr
from os import fdopen
from wsgiref.simple_server import make_server
import sys, os, json, traceback, requests

try:
  # if the directory 'virtualenv' is extracted out of a zip file
  path_to_virtualenv = os.path.abspath('./virtualenv')
  if os.path.isdir(path_to_virtualenv):
    # activate the virtualenv using activate_this.py contained in the virtualenv
    activate_this_file = path_to_virtualenv + '/bin/activate_this.py'
    if not os.path.exists(activate_this_file): # try windows path
      activate_this_file = path_to_virtualenv + '/Scripts/activate_this.py'
    if os.path.exists(activate_this_file):
      with open(activate_this_file) as f:
        code = compile(f.read(), activate_this_file, 'exec')
        exec(code, dict(__file__=activate_this_file))
    else:
      stderr.write("Invalid virtualenv. Zip file does not include 'activate_this.py'.\n")
      sys.exit(1)
except Exception:
  traceback.print_exc(file=sys.stderr, limit=0)
  sys.exit(1)

# now import the action as process input/output
from main__ import app as app

out = fdopen(3, "wb")
if os.getenv("__OW_WAIT_FOR_ACK", "") != "":
    out.write(json.dumps({"ok": True}, ensure_ascii=False).encode('utf-8'))
    out.write(b'\n')
    out.flush()

env = os.environ

global response_status
global response_headers
response_status = None
response_headers = None

def start_response(status, headers):
  global response_status
  global response_headers
  response_status = status
  response_headers = headers
  return []

environ = {
  "wsgi.url_scheme":"http",
  "wsgi.input":stdin,
  "wsgi.output":stdout,
  "wsgi.errors":stderr,
  "wsgi.multithread":True,
  "wsgi.multiprocess":True,
  "wsgi.run_once":False,
  "REQUEST_METHOD":"GET",
  "API_URL":"http://localhost:5000/",
  "PATH_INFO":"/",
  "QUERY_STRING":"",
  "CONTENT_TYPE":"application/json",
  #"request.args":json.dumps({}),
  #"request.body":json.dumps({}),
  #"request.headers":json.dumps({}),
  #"request.method":"GET",
  #"request.url":"http://localhost:5000/",
  #"request.path":"/",
  #"request.query_string":"",
  #"request.content_type":"application/json"
}
    
# Collect the response body
def build_response(response_iter):
  response_body = b''
  for chunk in response_iter:
    if isinstance(chunk, bytes):
      response_body += chunk
    else:
      response_body += chunk.encode('utf-8')
  
  return {
  #  "statusCode": response_status,
  #  "headers": response_headers,
    "body": response_body.decode('utf-8') if isinstance(response_body, bytes) else "test",
  }

while True:
  line = stdin.readline()
  if not line: break
  args = json.loads(line)

  res = {}    
  try:
    for key in args:
      if key == "value" and isinstance(args[key], dict):
        for k, v in args["value"].items():
          #environ[k] = v
          if k == "PREFERRED_URL_SCHEME":
            environ["wsgi.url_scheme"] = v
          elif k == "API_URL":
            environ["API_URL"] = v
          elif k == "method":
            environ["REQUEST_METHOD"] = v
          elif k in ["path", "__ow_path"]:
            environ["PATH_INFO"] = v
            environ["request.path"] = v
          elif k == "QUERY_STRING":
              environ["QUERY_STRING"] = v
      elif key == "value":
        environ["wsgi.input"] = args[key]
      else:
        env["__OW_%s" % key.upper()]= args[key]

    print(args, file=stdout)
    res = build_response(app(environ, start_response))
  except Exception as e:
    res = {"error": e}

  out.write(json.dumps(res, ensure_ascii=False).encode('utf-8'))
  out.write(b'\n')
  stdout.flush()
  stderr.flush()
  out.flush()

  """ 
  stdout: 
  {
  'wsgi.url_scheme': 'http', 
  'wsgi.input': <_io.TextIOWrapper name='<stdin>' mode='r' encoding='utf-8'>, 
  'wsgi.output': <_io.TextIOWrapper name='<stdout>' mode='w' encoding='utf-8'>, 
  'wsgi.errors': <_io.TextIOWrapper name='<stderr>' mode='w' encoding='utf-8'>, 
  'wsgi.multithread': True, 
  'wsgi.multiprocess': True,
  'wsgi.run_once': False,
  'REQUEST_METHOD': 'GET',
  'API_URL': 'http://localhost:5000/',
  'PATH_INFO': '/',
  'QUERY_STRING': '',
  'CONTENT_TYPE': 'application/json',
  '__ow_headers': {
    'accept': '*/*',
    'host': 'miniops.me',
    'user-agent': 'curl/7.81.0',
    'x-forwarded-for': '172.18.0.1',
    'x-forwarded-host': 'miniops.me',
    'x-forwarded-port': '80',
    'x-forwarded-proto': 'http',
    'x-forwarded-scheme': 'http',
    'x-real-ip': '172.18.0.1',
    'x-request-id': '1e4f1f155ece06c83508904a0dd27b2e',
    'x-scheme': 'http'
    },
  '__ow_method': 'get',
  '__ow_path': '/hello',
  'werkzeug.request': None
  }
   """
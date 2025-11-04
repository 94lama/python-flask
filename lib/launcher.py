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
from io import BytesIO
import base64
import urllib.parse
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
  "wsgi.url_scheme": "http",
  "wsgi.input": stdin,
  "wsgi.output": stdout,
  "wsgi.errors": stderr,
  "wsgi.multithread": False,
  "wsgi.multiprocess": True,
  "wsgi.run_once": True,
  "ACCEPT": "*/*",
  #"API_URL": "http://localhost:5000/",
  "PATH_INFO": "/",
  "CONTENT_TYPE": "application/json",
  "CONTENT_LENGTH": "0",
  "QUERY_STRING": "",
  "REQUEST_METHOD": "GET",
}

def reset_environ():
  environ["wsgi.input"]=stdin
  environ["ACCEPT"]="*/*"
  environ["CONTENT_TYPE"]="application/json"
  environ["CONTENT_LENGTH"] = "0"
  environ["PATH_INFO"] = "/"
  environ["QUERY_STRING"] = ""
  environ["REQUEST_METHOD"]="GET" #Resets the value in case the method is not specified


while True:
  line = stdin.readline()
  if not line: break
  args = json.loads(line)

  reset_environ()
  res = {}
  params = {}

  try:
    # Parse the input arguments to build the WSGI environ
    if isinstance(args["value"], dict):
      for k, v in args["value"].items():
        if k == "PREFERRED_URL_SCHEME": 
          environ["wsgi.url_scheme"] = v
        elif k == "API_URL": 
          environ["API_URL"] = v
        elif k == "method": 
          environ["REQUEST_METHOD"] = v.upper()
        # multiple values for PATH_INFO allows to cover both cli invocation and url requests
        elif k == "path": 
          environ["PATH_INFO"] = v
        elif not k.startswith("__ow_") and k not in ["action_name", "action_version", "activation_id", "deadline", "namespace", "transaction_id"]:
          # Collect query parameters
          query_params[k] = v
        # managing the headers
        elif k == "headers":
          if isinstance(v, dict):
            ct = v.get("content-type") or v.get("Content-Type")
            if ct: environ["CONTENT_TYPE"] = ct
            acc = v.get("accept") or v.get("Accept")
            if acc: environ["ACCEPT"] = acc
            xs = v.get("x-scheme") or v.get("X-Scheme")
            if xs: environ["wsgi.url_scheme"] = xs
        else:
          params[k] = v

    # Build body or query string from collected payload
    method = environ.get("REQUEST_METHOD", "GET").upper()
    ct = environ.get("CONTENT_TYPE", "").lower()
    
    if method in ["POST", "PUT", "PATCH", "DELETE"]:
      # Use the captured request body if available
      if request_body is not None:
        if isinstance(request_body, dict):
          body_bytes = json.dumps(request_body).encode("utf-8")
        elif isinstance(request_body, str):
          body_bytes = request_body.encode("utf-8")
        else:
          body_bytes = str(request_body).encode("utf-8")
      elif query_params:
        # If no body field but we have query_params, use them as body for POST
        if "json" in ct:
          body_bytes = json.dumps(query_params).encode("utf-8")
        elif "form-urlencoded" in ct:
          body_bytes = urllib.parse.urlencode(query_params, doseq=True).encode("utf-8")
        else:
          body_bytes = json.dumps(query_params).encode("utf-8")
      
      environ["CONTENT_LENGTH"] = str(len(body_bytes))
    
    # Build query string from query_params (for GET or as additional params for other methods)
    if query_params:
      environ["QUERY_STRING"] = urllib.parse.urlencode(query_params, doseq=True)

    environ["wsgi.input"] = BytesIO(body_bytes)

    response_body = ""
    response = app(environ, start_response)
    if response.json:
      response_body = json.dumps(response.json).encode('utf-8')
    else:
      for chunk in response:
        if isinstance(chunk, str):
          chunk = chunk.encode('utf-8')
        response_body += chunk
  except Exception as e:
    stderr.write(f"Error building response: {e}\n")
    response_body = f'Error building response: {e}'.encode('utf-8')

  """ res = {
    "statusCode": response_status,
    "headers": response_headers,
    "body": response_body
  } """
  res = "ok"#response_body.decode('utf-8')

  out.write(json.dumps(res, ensure_ascii=False).encode('utf-8'))
  out.write(b'\n')
  stdout.flush()
  stderr.flush()
  out.flush()

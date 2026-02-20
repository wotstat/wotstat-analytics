import threading

import BigWorld
import functools

try: import openwg_network
except ImportError: openwg_network = None

json_headers = {
  'Content-type': 'application/json',
  'Accept': 'application/json'
}

API_URL_PREFIX = 'https://wotstat.info'
SERVERS_BASE_URL = [
  'https://wotstat.info',
  'https://ru.wotstat.info',
  'https://wotstat-proxy.ru',
  'http://wotstat-proxy.ru'
]

currentServerIndex = 0


# OPENWG

OPEN_WG_PROXY_URLS = [
  'https://wotstat.info',
  'https://loki.wotstat.info'
]

useOpenWG = openwg_network is not None

def openWGRequest(url, method='GET', headers=None, timeout=30.0, body=None, callback=None):
  def worker():
    try:
      resp = openwg_network.request(url, method, headers, timeout, body)
      if callback: BigWorld.callback(0.0, functools.partial(callback, resp))
    except Exception as e:
      print("[WOTSTAT ANALYTICS] OpenWG request exception for url %s: %s" % (url, str(e)))
      if callback:
        resp = (500, {}, None)
        BigWorld.callback(0.0, functools.partial(callback, resp))

  t = threading.Thread(target=worker)
  t.daemon = True
  t.start()

def shouldUseOpenWG(url):
  return useOpenWG and any(url.startswith(proxyUrl) for proxyUrl in OPEN_WG_PROXY_URLS)

def cancelOpenWGRequests():
  global useOpenWG
  useOpenWG = False
  print("[WOTSTAT ASYNC] OpenWG requests cancelled, switching to BigWorld.fetchURL")

# ================

def next_server_index():
  global currentServerIndex
  currentServerIndex = (currentServerIndex + 1) % len(SERVERS_BASE_URL)
  return currentServerIndex

def getApiUrl(url):
  if shouldUseOpenWG(url):
    return url
  
  if url.startswith(API_URL_PREFIX):
    return url.replace(API_URL_PREFIX, SERVERS_BASE_URL[currentServerIndex], 1)
  return url

def get_async_api(url, headers={}, callback=None, error_callback=None, attempt=2):
  def on_error(res):
    next_server_index()
    if attempt > 0: get_async_api(url, headers, callback, error_callback, attempt - 1)
    elif error_callback: error_callback(res)

  get_async(getApiUrl(url), headers, callback, on_error)

def post_async_api(url, data=None, headers={}, callback=None, error_callback=None, attempt=0):
  def on_error(res):
    next_server_index()
    if attempt > 0: post_async_api(url, data, headers, callback, error_callback, attempt - 1)
    elif error_callback: error_callback(res)

  post_async(getApiUrl(url), data, headers, callback, on_error)

def get_async(url, headers={}, callback=None, error_callback=None):
  request_async(
    method='GET',
    url=url,
    headers=headers,
    postData=None,
    callback=callback,
    error_callback=error_callback
  )

def post_async(url, data=None, headers={}, callback=None, error_callback=None):
  request_async(
    method='POST',
    url=url,
    headers=headers,
    postData=data,
    callback=callback,
    error_callback=error_callback
  )

def request_async(method, url, headers, postData, callback, error_callback=None):

  def onComplete(result):
    # type: (BigWorld.PyURLResponse) -> None
    if result.responseCode != 200:
      if error_callback: error_callback(result)
      return
    else:
      if callback: callback(result.body)
      return
  
  def onOpenWGComplete(response):
    status, headers, body = response

    result = type('Result', (object,), {})()
    result.responseCode = status
    result.headers = headers
    result.body = body

    if status != 200:
      cancelOpenWGRequests()

    onComplete(result)

  if shouldUseOpenWG(url):
    openWGRequest(url, callback=onOpenWGComplete, method=method, headers=headers, body=postData, timeout=10.0)
  else:
    BigWorld.fetchURL(url, onComplete, method=method, headers=headers, postData=postData, timeout=10.0)

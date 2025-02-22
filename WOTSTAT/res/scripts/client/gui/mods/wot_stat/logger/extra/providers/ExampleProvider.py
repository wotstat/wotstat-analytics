import BigWorld

from ..IExtraProvider import IExtraProvider

class ExampleProvider(IExtraProvider):
   
  def __init__(self):
    pass
  
  def setup(self):
    pass
  
  def getExtraData(self):
    try:
      return {}
    except Exception:
      return {}
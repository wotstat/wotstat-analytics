

class IExtraProvider(object):
  def getExtraData(self): 
    raise NotImplementedError
  
  def setup(self):
    raise NotImplementedError

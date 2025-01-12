
from Singleton import Singleton
from typing import List
from .IExtraProvider import IExtraProvider


class ExtraCollector(Singleton):
  
  @staticmethod
  def instance():
      return ExtraCollector()
  
  def _singleton_init(self):
    self._collectors = [] # type: List[IExtraProvider]
    
    try:
      from .BobProvider import BobProvider
      self._collectors.append(BobProvider())
    except ImportError: pass
    
  def getExtraData(self):
    data = {}
    
    for collector in self._collectors:
      data.update(collector.getExtraData())
      
    return data
  
  def setup(self):
    for collector in self._collectors:
      collector.setup()
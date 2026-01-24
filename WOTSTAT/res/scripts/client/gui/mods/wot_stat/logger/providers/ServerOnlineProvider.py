from PlayerEvents import g_playerEvents

from ...common.exceptionSending import with_exception_sending

class ServerOnlineProvider():
  
  def __init__(self):
    
    self.serverOnline = 0
    self.regionOnline = 0
    
    g_playerEvents.onServerStatsReceived += self.onStatsReceived
    
  @with_exception_sending
  def onStatsReceived(self, stats):
    parsed = dict(stats)
    self.serverOnline = parsed.get('clusterCCU', 0)
    self.regionOnline = parsed.get('regionCCU', 0)
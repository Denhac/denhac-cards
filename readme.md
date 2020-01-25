# Card Auto Add

The goal of this project is to automatically add member cards to a WinDSX database. It runs on startup and uses the WinDSX API to talk to the system. It's still in its infancy and could use some TLC.


## Instructions:
Our goal is to create a Windows "service" (not an actual service) that can run in the background on a machine running WinDSX and add cards without any user interaction. Since the version of WinDSX this was made for has an API, we write to that API format. Unfortunately, the program needs to be opened and logged into so this service tries to manage that as well.
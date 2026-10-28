# =================================================================================================
# Contributing Authors:	    Drason Swihart
#                           Paola Martinez
#                           Robert Pike
# Email Addresses:          dpsw224@uky.edu
#                           paola.mar@uky.edu
#                           rfpi223@uky.edu
# Date:                     10/28/2026
# Purpose:                  Server code: Accepts both clients · Uses threads · Relays paddle positions, ball location, and score
# Misc:                     <Not Required.  Anything else you might want to include>
# =================================================================================================

import socket
import threading
import json

HOST = "0.0.0.0"
PORT = 5000



# Use this file to write your server logic
# You will need to support at least two clients
# You will need to keep track of where on the screen (x,y coordinates) each paddle is, the score 
# for each player and where the ball is, and relay that to each client
# I suggest you use the sync variable in pongClient.py to determine how out of sync your two
# clients are and take actions to resync the games

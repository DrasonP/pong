# =================================================================================================
# Contributing Authors:	    <Drason Swihart, Paola Martinez, Robert Pike>
# Email Addresses:          <dpsw224@uky.edu , paola.mar@uky.edu, rfpi223@uky.edu>
# Date:                     10/28/2026
# Purpose:                  Client code: Each client will send paddle position · Receives game state
# Misc:                     <Not Required.  Anything else you might want to include>
# =================================================================================================

import pygame
import tkinter as tk
import sys
import socket
import json

from assets.code.helperCode import *

#Send JSON message
def sendMessage(client, message):
    data = json.dumps(message) + "\n"   #Convert message into json
    client.sendall(data.encode("utf-8"))  #Send data to server 

#Recieve JSON message 
def recieveMessage(stream):
    data = stream.readline()  #Read the stream to get the data send by the server

    if not data:   #If recieved json isn't data then raise an error
        raise ConnectionError("Server disconnected")

    return json.loads(data.decode("utf-8"))   #Convert json back into message


# This is the main game loop.  For the most part, you will not need to modify this.  The sections
# where you should add to the code are marked.  Feel free to change any part of this project
# to suit your needs.
def playGame(screenWidth:int, screenHeight:int, playerPaddle:str, client:socket.socket, stream) -> None:
    
    # Pygame inits
    pygame.mixer.pre_init(44100, -16, 2, 2048)
    pygame.init()

    # Constants
    WHITE = (255,255,255)
    clock = pygame.time.Clock()
    scoreFont = pygame.font.Font("./assets/fonts/pong-score.ttf", 32)
    winFont = pygame.font.Font("./assets/fonts/visitor.ttf", 48)
    pointSound = pygame.mixer.Sound("./assets/sounds/point.wav")
    bounceSound = pygame.mixer.Sound("./assets/sounds/bounce.wav")

    # Display objects
    screen = pygame.display.set_mode((screenWidth, screenHeight))
    winMessage = pygame.Rect(0,0,0,0)
    topWall = pygame.Rect(-10,0,screenWidth+20, 10)
    bottomWall = pygame.Rect(-10, screenHeight-10, screenWidth+20, 10)
    centerLine = []
    for i in range(0, screenHeight, 10):
        centerLine.append(pygame.Rect((screenWidth/2)-5,i,5,5))

    # Paddle properties and init
    paddleHeight = 50
    paddleWidth = 10
    paddleStartPosY = (screenHeight/2)-(paddleHeight/2)
    leftPaddle = Paddle(pygame.Rect(10,paddleStartPosY, paddleWidth, paddleHeight))
    rightPaddle = Paddle(pygame.Rect(screenWidth-20, paddleStartPosY, paddleWidth, paddleHeight))

    ball = Ball(pygame.Rect(screenWidth/2, screenHeight/2, 5, 5), -5, 0)

    if playerPaddle == "left":
        opponentPaddleObj = rightPaddle
        playerPaddleObj = leftPaddle
    else:
        opponentPaddleObj = leftPaddle
        playerPaddleObj = rightPaddle

    #Score variables
    lScore = 0
    rScore = 0

    #Sync and play again variables
    sync = 0
    play_again_requested = False

    try: 
        while True:
            # Wiping the screen
            screen.fill((0,0,0))

            # Getting keypress events
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_DOWN:
                        playerPaddleObj.moving = "down"

                    elif event.key == pygame.K_UP:
                        playerPaddleObj.moving = "up"

                    elif event.key == pygame.K_r:
                        if lScore > 4 or rScore > 4:
                            play_again_requested = True

                elif event.type == pygame.KEYUP:
                    playerPaddleObj.moving = ""

            # Update the player paddle and opponent paddle's location on the screen
            if playerPaddleObj.moving == "down":
                if playerPaddleObj.rect.bottomleft[1] < screenHeight-10:
                    playerPaddleObj.rect.y += playerPaddleObj.speed
            elif playerPaddleObj.moving == "up":
                if playerPaddleObj.rect.topleft[1] > 10:
                    playerPaddleObj.rect.y -= playerPaddleObj.speed

            # If the game is over, display the win message
            if lScore > 4 or rScore > 4:
                winText = "Player 1 Wins! " if lScore > 4 else "Player 2 Wins! "
                textSurface = winFont.render(winText, False, WHITE, (0,0,0))
                textRect = textSurface.get_rect()
                textRect.center = ((screenWidth/2), screenHeight/2)
                winMessage = screen.blit(textSurface, textRect)
            else:

                # ==== Ball Logic =====================================================================
                ball.updatePos()

                # If the ball makes it past the edge of the screen, update score, etc.
                if ball.rect.x > screenWidth:
                    lScore += 1
                    pointSound.play()
                    ball.reset(nowGoing="left")
                elif ball.rect.x < 0:
                    rScore += 1
                    pointSound.play()
                    ball.reset(nowGoing="right")
                
                # If the ball hits a paddle
                if ball.rect.colliderect(playerPaddleObj.rect):
                    bounceSound.play()
                    ball.hitPaddle(playerPaddleObj.rect.center[1])
                elif ball.rect.colliderect(opponentPaddleObj.rect):
                    bounceSound.play()
                    ball.hitPaddle(opponentPaddleObj.rect.center[1])
                
                # If the ball hits a wall
                if ball.rect.colliderect(topWall) or ball.rect.colliderect(bottomWall):
                    bounceSound.play()
                    ball.hitWall()
            
                pygame.draw.rect(screen, WHITE, ball)
                # ==== End Ball Logic =================================================================

            # Drawing the dotted line in the center
            for i in centerLine:
                pygame.draw.rect(screen, WHITE, i)
        
            # Drawing the player's new location
            for paddle in [playerPaddleObj, opponentPaddleObj]:
                pygame.draw.rect(screen, WHITE, paddle)

            pygame.draw.rect(screen, WHITE, topWall)
            pygame.draw.rect(screen, WHITE, bottomWall)
            scoreRect = updateScore(lScore, rScore, screen, WHITE, scoreFont)
            pygame.display.update()
            clock.tick(60)
        
            # =========================================================================================
            # Send your server update here at the end of the game loop to sync your game with your
            # opponent's game
            # =========================================================================================

            #Send ball, paddle, and score info to server
            sync += 1

            message = {
                "paddle": {
                    "x": playerPaddleObj.rect.x,
                    "y": playerPaddleObj.rect.y
                },
                "ball": {
                    "x": ball.rect.x,
                    "y": ball.rect.y,
                    "xVel": ball.xVel,
                    "yVel": ball.yVel
                },
                "scores": {
                    "left": lScore,
                    "right": rScore
                },
                "sync": sync,
                "action": "play_again" if play_again_requested else None
            }

            # The request is sent only once.
            play_again_requested = False

            sendMessage(client, message)

            #Recieve opponent info from Server
            serverData = recieveMessage(stream)

            # Update opponent paddle
            if playerPaddle == "left":
                opponentSide = "right"
            else:
                opponentSide = "left"

            opponentPaddleObj.rect.x = serverData["paddles"][opponentSide]["x"]
            opponentPaddleObj.rect.y = serverData["paddles"][opponentSide]["y"]

            # Update ball position and velocity
            ball.rect.x = serverData["ball"]["x"]
            ball.rect.y = serverData["ball"]["y"]
            ball.xVel = serverData["ball"]["xVel"]
            ball.yVel = serverData["ball"]["yVel"]

            # Update scores
            lScore = serverData["scores"]["left"]
            rScore = serverData["scores"]["right"]

            # Synchronize game counters
            sync = max(serverData["sync"]["left"], serverData["sync"]["right"])
            # Handle a new round starting.
            if serverData.get("reset", False):
            
                # Reset scores.
                lScore = 0
                rScore = 0
            
                # Reset paddles.
                leftPaddle.rect.x = 10
                leftPaddle.rect.y = paddleStartPosY
            
                rightPaddle.rect.x = screenWidth - 20
                rightPaddle.rect.y = paddleStartPosY
            
                # Reset the ball.
                ball.reset(nowGoing="left")
            
                # Stop any paddle movement.
                leftPaddle.moving = ""
                rightPaddle.moving = ""
            
                # Reset the local synchronization counter.
                sync = max(
                    serverData["sync"]["left"],
                    serverData["sync"]["right"]
                )

    except(OSError, ConnectionError, json.JSONDecodeError) as error:
        errorLabel.config(text=f"Connection error: {error}")
        errorLabel.update()

    finally:
        stream.close()
        client.close()

        pygame.quit()



# This is where you will connect to the server to get the info required to call the game loop.  Mainly
# the screen width, height and player paddle (either "left" or "right")
# If you want to hard code the screen's dimensions into the code, that's fine, but you will need to know
# which client is which
def joinServer(ip:str, port:str, errorLabel:tk.Label, app:tk.Tk) -> None:
    # Purpose:      This method is fired when the join button is clicked
    # Arguments:
    # ip            A string holding the IP address of the server
    # port          A string holding the port the server is using
    # errorLabel    A tk label widget, modify it's text to display messages to the user (example below)
    # app           The tk window object, needed to kill the window
    
    # Create a socket and connect to the server
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try: 
        client.connect((ip, int(port)))
        stream = client.makefile("rwb")

        # Get the required information from your server (screen width, height & player paddle, "left or "right)
        serverData = recieveMessage(stream)

        screenWidth = serverData["screen_width"]
        screenHeight = serverData["screen_height"]
        playerPaddle = serverData["player_paddle"]

        errorLabel.config(text="Connected! Starting game...")
        errorLabel.update()
      
        # Close this window and start the game with the info passed to you from the server
        app.withdraw()     # Hides the window
        playGame(screenWidth, screenHeight, playerPaddle, client, stream)  #Starts the game
        app.quit()         # Kills the window

    except (OSError, ValueError, KeyError, ConnectionError, json.JSONDecodeError) as error:
        errorLabel.config(text=f"Connection Failed: {error}")
        errorLabel.update()

        client.close()


# This displays the opening screen, you don't need to edit this (but may if you like)
def startScreen():
    app = tk.Tk()
    app.title("Server Info")

    image = tk.PhotoImage(file="./assets/images/logo.png")

    titleLabel = tk.Label(image=image)
    titleLabel.grid(column=0, row=0, columnspan=2)

    ipLabel = tk.Label(text="Server IP:")
    ipLabel.grid(column=0, row=1, sticky="W", padx=8)

    ipEntry = tk.Entry(app)
    ipEntry.grid(column=1, row=1)

    portLabel = tk.Label(text="Server Port:")
    portLabel.grid(column=0, row=2, sticky="W", padx=8)

    portEntry = tk.Entry(app)
    portEntry.grid(column=1, row=2)

    errorLabel = tk.Label(text="")
    errorLabel.grid(column=0, row=4, columnspan=2)

    joinButton = tk.Button(text="Join", command=lambda: joinServer(ipEntry.get(), portEntry.get(), errorLabel, app))
    joinButton.grid(column=0, row=3, columnspan=2)

    app.mainloop()

if __name__ == "__main__":
    startScreen()

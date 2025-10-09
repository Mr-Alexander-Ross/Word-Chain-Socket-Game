# Word Chain Game Client
# Version 1.0 Basic 2-player word chain game
# Author: Alexander, Brandon, Jorie
# Date: 10/9/2025

from socket import *
import os

def clear_screen():
    # Clear the terminal screen (Windows/Unix)
    os.system("cls" if os.name == "nt" else "clear")

def client_main():
    serverIP = "localhost"
    serverPort = 12005
    clientSocket = socket(AF_INET, SOCK_STREAM)
    clientSocket.connect((serverIP, serverPort))

    while True:
        # Receive message from server
        message = clientSocket.recv(1024).decode()
        clear_screen()
        print(message)
        if "Your turn" in message:
            word = input("Enter your word: ")
            clientSocket.send(word.encode())
        elif "Game over" in message or not message:
            break

    clientSocket.close()

client_main()
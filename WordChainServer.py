# Word Chain Game Server
# Version 1.0 Basic 2-player word chain game
# Author: Alexander, Brandon, Jorie
# Date: 10/9/2025
# Updated: 10/15/2025 - Updated to handle timer expiration from clients



from socket import *
from _thread import *
import os
import enchant  # Add PyEnchant

def load_dictionary():
    # Use PyEnchant English dictionary
    return enchant.Dict("en_US")

#Store Game records in WordChainRecords.txt. 
def store_record(winner : str,loser : str,round_num : int):
    file = open("WordChainRecords.txt","a+")
    file.close()
    with open("WordChainRecords.txt","r+") as f:
        document = f.readlines()
        if len(document) == 0:                              #if file is empty, no need to check for existing users
            winner_record = f"{winner},1,0,{round_num}\n"   #Create user records
            loser_record = f"{loser},0,1,{round_num}\n"     
            document.append(winner_record)                  #append user records to document
            document.append(loser_record)                   
            f.writelines(document)                          #rewrite document
            return 
        winner_updated = False
        loser_updated = False
        new_document = []
    
        for line in document: #Stores all lines in f as an array (uses endline characters as separators)
            split_line = line.split(',')
            if split_line[0].lower() == winner.lower() and not winner_updated:
                if int(split_line[3]) < round_num:                      #if the player gets a new high score  
                    #update the high score
                    split_line[3] = str(round_num) + '\n'
                split_line[1] = str(int(split_line[1]) + 1)           
                line = []
                for entry in split_line:        # update the win counter
                    line += entry + ','
                line = ''.join(line).strip(',')
                winner_updated = True
                
            if split_line[0].lower() == loser.lower() and not loser_updated: #same as above but for the losing player
                if int(split_line[3]) < round_num:
                    split_line[3] = str(round_num) + '\n'
                split_line[2] = str(int(split_line[2]) + 1)
                line = []
                for entry in split_line:
                    line += entry + ','
                line = ''.join(line).strip(',')
                loser_updated = True
            new_document.append(line)
                
        #If there is no matching record 
        if not winner_updated:
            new_document.append(f"{winner},1,0,{round_num}\n")
        if not loser_updated:
            new_document.append(f"{loser},0,1,{round_num}\n")
    #write edited file to document
    with open("WordChainRecords.txt","w+") as f:
        f.writelines(new_document)


def word_chain_thread(player1, player2, dictionary):
    print("Starting Word Chain game thread")
    used_words = []
    current_player = player1
    other_player = player2
    last_letter = None
    round_num = 1

    # Start the game
    player1.send("Welcome to Word Chain! You are Player 1.\n".encode())
    player2.send("Welcome to Word Chain! You are Player 2.\n".encode())
    player1.send("Game starts! Please enter the first word:\n".encode())
    player2.send("Waiting for Player 1 to start...\n".encode())

    while True:
        round_num += 1 #increment round counter by 1
        # Ask current player for a word
        current_player.send("Your turn.\n".encode())
        word = current_player.recv(1024).decode().strip().lower()
        
        if word == "timerexpired":
            # Handle timer expiration
            current_player.send("Time expired!\n".encode())
            other_player.send("Opponent's time expired!\n".encode())
            break
        # Check if word is valid using PyEnchant
        if not dictionary.check(word):
            current_player.send(f"{word} is an Invalid word.\n".encode())
            break
        if word in used_words:
            current_player.send(f"{word} already used.\n".encode())
            break
        if last_letter and word[0] != last_letter:
            current_player.send(f"Word must start with '{last_letter}'.\n".encode())
            break

        # Word is valid
        used_words.append(word)
        last_letter = word[-1]
        current_player.send(f"Accepted!\n".encode())
        other_player.send(f"Player used '{word}'.\n".encode())

        # Swap players
        current_player, other_player = other_player, current_player
    current_player.send("You lose! Other player entering name, please wait.")
    other_player.send("You win! Please Enter Your Name: ")
    winner_name = other_player.recv(1024).decode().strip().lower()
    current_player.send("Please Enter Your Name: ")
    loser_name = current_player.recv(1024).decode().strip().lower

    current_player.send("Game over!\n".encode())
    other_player.send("Game over!\n".encode())
    store_record(winner_name,loser_name,round_num//2) #store game record

def server_main():
    serverPort = 12005
    serverSocket = socket(AF_INET, SOCK_STREAM)
    serverSocket.bind(("", serverPort))
    serverSocket.listen(2)
    print("Word Chain server is ready!")

    dictionary = load_dictionary()

    while True:
        print("Waiting for two players to connect...")
        player1, addr1 = serverSocket.accept()
        print("Player 1 connected.")
        player2, addr2 = serverSocket.accept()
        print("Player 2 connected.")
        start_new_thread(word_chain_thread, (player1, player2, dictionary))

server_main()
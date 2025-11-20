# Word Chain Game Server
# Version 1.0 Basic 2-player word chain game
# Author: Alexander, Brandon, Jorie
# Date: 10/9/2025
# Updated: 10/15/2025 - Updated to handle timer expiration from clients
# Updated: 10/20/2025 - Added rematch prompt with timeout
#                     - Added input timeout handling for rematch prompt



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
    player1.settimeout(15)
    player2.settimeout(15)

    play_again = True
    while play_again:  # Outer loop for multiple games
        # Reset game state for each new game
        used_words = []
        current_player = player1
        other_player = player2
        current_is_p1 = True  # Track which player is current
        last_letter = None
        cp_message = ""
        op_message = ""
        round_num = 0  # Initialize round counter for this game

        # Start the game
        player1.send("Welcome to Word Chain! You are Player 1.\n".encode())
        player2.send("Welcome to Word Chain! You are Player 2.\n".encode())
        player1.send("Game starts! Please enter the first word:\n".encode())
        player2.send("Waiting for Player 1 to start...\n".encode())

        # Inner game loop (existing logic)
        while True:
            round_num += 1  # Increment round counter for each turn
            current_player.send("Your turn.\n".encode())
            try:
                data = current_player.recv(1024)
                if not data:
                    # Socket closed by client
                    play_again = False
                    print("A player disconnected during the game.")
                    break
                word = data.decode().strip().lower()
                # If the client sent an empty string (pressed enter with no word),
                # treat as an invalid move rather than a socket close to avoid
                # downstream errors in word validation.
                if word == "":
                    cp_message = "No word entered. "
                    op_message = "Opponent failed to enter a word. "
                    break
            except timeout:
                word = "timerexpired"
            
            if word == "timerexpired":
                cp_message = "Time expired! "
                op_message = "Opponent's time expired! "
                break
            # Check if word is valid using PyEnchant
            if not dictionary.check(word):
                cp_message = f"{word} is an Invalid word. "
                op_message = f"Opponent used invalid word '{word}'. "
                break
            if word in used_words:
                cp_message = f"{word} already used. "
                op_message = f"Opponent tried to use '{word}' which has already been used. "
                break
            if last_letter and word[0] != last_letter:
                cp_message = f"Word must start with '{last_letter}'. "
                op_message = f"Opponent tried to use '{word}' which does not start with '{last_letter}'. "
                break

            # Word is valid
            used_words.append(word)
            last_letter = word[-1]
            current_player.send(f"Accepted!\n".encode())
            other_player.send(f"Player used '{word}'.\n".encode())
            #INSERT ROUND COUNTER HERE

            # Swap players
            current_player, other_player = other_player, current_player
            current_is_p1 = not current_is_p1

        # Game over - determine winner
        cp_message += "\nGame over! You lost.\n"
        op_message += "\nGame over! You won!\n"
        # Send messages relative to current/other (current_player lost in this design)
        try:
            current_player.send(cp_message.encode())
        except Exception:
            pass
        try:
            other_player.send(op_message.encode())
        except Exception:
            pass
        print(f"Game over. Current message: {cp_message.strip()} | Other message: {op_message.strip()}")

        # Rematch prompt
        current_player.send("Rematch?\n".encode())
        other_player.send("Rematch?\n".encode())
        print("Sent rematch prompts to both players")

        # Receive rematch responses from the current and other player (in that order)
        try:
            response1 = current_player.recv(1024).decode().strip().lower()
            if not response1:
                play_again = False
                print(f"Current player disconnected during rematch prompt")
                break
            print(f"Current player rematch response: {response1}")
        except timeout:
            response1 = "no"
            print("Current player timeout on rematch prompt")
        except Exception as e:
            play_again = False
            print(f"Error receiving from current player: {e}")
            break

        try:
            response2 = other_player.recv(1024).decode().strip().lower()
            if not response2:
                play_again = False
                print(f"Other player disconnected during rematch prompt")
                break
            print(f"Other player rematch response: {response2}")
        except timeout:
            response2 = "no"
            print("Other player timeout on rematch prompt")
        except Exception as e:
            play_again = False
            print(f"Error receiving from other player: {e}")
            break

        # Decide whether to play again
        if response1 == "yes" and response2 == "yes":
            print("Both players agreed to rematch!")
            try:
                current_player.send("Starting new game...\n".encode())
            except Exception:
                pass
            try:
                other_player.send("Starting new game...\n".encode())
            except Exception:
                pass
            # Loop continues, resetting game state
        else:
            play_again = False
            print(f"Rematch declined. current: {response1}, other: {response2}")

        # If rematch was declined or players disconnected, collect names and store record
        if not play_again:
            try:
                current_player.send("Please enter your name for the record: ".encode())
                loser_name = current_player.recv(1024).decode().strip().lower()
            except Exception:
                loser_name = "Unknown"

            try:
                other_player.send("Please enter your name for the record: ".encode())
                winner_name = other_player.recv(1024).decode().strip().lower()
            except Exception:
                winner_name = "Unknown"

            # Store the game record
            store_record(winner_name, loser_name, round_num // 2)

            # Now send goodbye messages
            try:
                current_player.send("Thanks for playing!\n".encode())
            except Exception:
                pass
            try:
                other_player.send("Thanks for playing!\n".encode())
            except Exception:
                pass

    # Close connections
    try:
        player1.close()
        player2.close()
        print("Game ended... Connections closed")
    except Exception:
        pass

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
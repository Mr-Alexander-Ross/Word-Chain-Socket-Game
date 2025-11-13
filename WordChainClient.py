# Word Chain Game Client
# Version 1.0 Basic 2-player word chain game
# Author: Alexander, Brandon, Jorie
# Date: 10/9/2025
# Updated: 10/15/2025 - Added countdown timer for player turns

from socket import *
import os
import threading
import time
import sys
import queue

def clear_screen():
    # Clear the terminal screen (Windows/Unix)
    os.system("cls" if os.name == "nt" else "clear")


def clear_status_line():
    """Clear the reserved timer/status line above the prompt using ANSI if
    available. Falls back to printing a blank line.
    """
    try:
        # move up one line, move to column 1 and clear it
        sys.stdout.write('\x1b[1A')
        sys.stdout.write('\x1b[1G')
        sys.stdout.write('\x1b[2K')
        sys.stdout.flush()
    except Exception:
        # fallback: print a blank line (may not remove the old text)
        print()


def countdown_timer(client_socket, response_event, timeout_seconds):
    """Countdown timer that sends 'TimerExpired' to the server socket if
    `response_event` isn't set before `timeout_seconds` elapse. Prints a
    simple per-second countdown to stdout.
    """
    # Loop once per second, updating the status line each tick.
    # If response_event is set by the main thread (player responded) the
    # timer exits early. If the timer reaches zero it sends a
    # "TimerExpired" message to the server and sets the event itself so
    # that the main thread knows the timeout already occurred.
    for remaining in range(timeout_seconds, 0, -1):
        if response_event.is_set():
            # Stop timer if response received
            return
        # Try to update a single status line above the prompt using ANSI
        # save/restore cursor. If the terminal doesn't support it, fall back
        # to printing a line (less pretty).
        try:
            # save cursor, move up 1, go to column 1, clear line, print status in
            # a fixed position (no newline), then restore cursor so the user's
            # typing position is unchanged.
            sys.stdout.write('\x1b[s')      # save cursor
            sys.stdout.write('\x1b[1A')     # move up one line (the reserved status line)
            sys.stdout.write('\x1b[1G')     # move to column 1
            sys.stdout.write('\x1b[2K')     # clear entire line
            # Write the status without newline so we don't affect the input line
            sys.stdout.write(f"Time left: {remaining:2d}s")
            sys.stdout.write('\x1b[u')      # restore cursor
            sys.stdout.flush()
        except Exception:
            # Fallback: simple print (will add lines)
            print(f"Time left: {remaining:2d}s")
        # Wait one second between updates
        time.sleep(1)

    if not response_event.is_set():
        # Timer reached zero and nobody responded: notify server.
        print("\nTime expired! Sending timer expired to server.")
        client_socket.send("TimerExpired".encode())
        response_event.set()
        # Clear the reserved status line so it doesn't show a stale timer.
        try:
            sys.stdout.write('\x1b[1A')
            sys.stdout.write('\x1b[1G')
            sys.stdout.write('\x1b[2K')
            sys.stdout.flush()
        except Exception:
            pass
        try:
            sys.stdout.write('\x1b[1A')
            sys.stdout.write('\x1b[2K')
            sys.stdout.flush()
        except Exception:
            pass

def client_main():
    serverIP = "localhost"
    serverPort = 12005
    clientSocket = socket(AF_INET, SOCK_STREAM)
    clientSocket.connect((serverIP, serverPort))

    # Start a background thread to receive messages and put them into a queue.
    message_queue = queue.Queue()

    def socket_receiver(sock, msg_queue):
        while True:
            data = sock.recv(1024)
            if not data:
                print("\nConnection closed by server.")
                os._exit(0)
            text = data.decode()
            # Print immediately so messages show even if main thread is blocked on input
            print("\n" + text)
            msg_queue.put(text)
            if "Game over" in text:
                sock.close()
                os._exit(0)

    recv_thread = threading.Thread(target=socket_receiver, args=(clientSocket, message_queue), daemon=True)
    recv_thread.start()

    # Command input queue and thread: allows user to type lobby commands while
    # the receiver thread prints incoming server messages.
    command_queue = queue.Queue()

    def input_reader(cmd_queue):
        """Read lines from stdin and put them in the command queue."""
        while True:
            try:
                line = input()
            except (EOFError, KeyboardInterrupt):
                # Propagate a quit command so main loop can exit cleanly
                cmd_queue.put('quit')
                return
            cmd_queue.put(line)

    input_thread = threading.Thread(target=input_reader, args=(command_queue,), daemon=True)
    input_thread.start()

    # Client state: 'lobby' or 'game'
    mode = 'lobby'
    print("Type 'help' for available commands. In lobby mode you can: list, create <lobby> <name>, join <lobby> <name>, leave <lobby> <name>, quit")

    try:
        while True:
            # Prefer handling server messages first so state changes (like START_GAME)
            # are acted upon immediately. We use short timeouts to allow responsive
            # handling of both queues without busy-waiting.
            try:
                message = message_queue.get(timeout=0.1)
            except queue.Empty:
                message = None

            if message:
                clear_screen()
                print(message)
                # If server tells us a game is starting, switch to game mode.
                if message.strip().startswith('START_GAME'):
                    mode = 'game'
                    print('Game starting — switching to game mode.')
                    # Continue loop; in-game prompts are triggered by server 'Your turn'
                elif 'Your turn' in message and mode == 'game':
                    # Start turn flow (existing logic)
                    timeout_seconds = 10
                    response_sent_event = threading.Event()

                    # Reserve a status line above the prompt for the timer
                    print()  # blank line reserved for timer status
                    sys.stdout.write('Enter a word: ')
                    sys.stdout.flush()

                    timer_thread = threading.Thread(target=countdown_timer, args=(clientSocket, response_sent_event, timeout_seconds), daemon=True)
                    timer_thread.start()

                    # Wait for the player's input from the command queue. This uses
                    # blocking get so the main thread can still be responsive to other
                    # short events (like timer setting the event).
                    try:
                        # If input_reader places lines in queue, get the next one as the word.
                        word = command_queue.get()
                    except Exception:
                        word = ''

                    if not response_sent_event.is_set():
                        clientSocket.send(word.encode())
                        response_sent_event.set()
                    else:
                        print('Input ignored because time already expired.')
                elif 'Game over' in message:
                    print('Server indicated game over. Exiting.')
                    break

            # Handle user-typed commands when in lobby mode (or general commands)
            try:
                cmd = command_queue.get_nowait()
            except queue.Empty:
                cmd = None

            if cmd:
                cmd = cmd.strip()
                if cmd.lower() == 'quit':
                    print('Quitting client.')
                    break
                if cmd.lower() == 'help':
                    print("Commands:\n  list\n  create <lobby> <your_name>\n  join <lobby> <your_name>\n  leave <lobby> <your_name>\n  quit")
                    continue

                # If we're in game mode, player input during a turn is handled above
                if mode == 'game':
                    # If user types during the game outside of a 'Your turn' prompt,
                    # just send the raw line to the server (some server messages are free-form)
                    clientSocket.send(cmd.encode())
                    continue

                # Lobby mode commands parsing
                parts = cmd.split()
                if not parts:
                    continue
                verb = parts[0].lower()
                if verb == 'list':
                    clientSocket.send('LIST_LOBBIES'.encode())
                elif verb == 'create' and len(parts) >= 3:
                    lobby_name = parts[1]
                    player_name = ' '.join(parts[2:])
                    clientSocket.send(f'CREATE_LOBBY {lobby_name} {player_name}'.encode())
                elif verb == 'join' and len(parts) >= 3:
                    lobby_name = parts[1]
                    player_name = ' '.join(parts[2:])
                    clientSocket.send(f'JOIN_LOBBY {lobby_name} {player_name}'.encode())
                elif verb == 'leave' and len(parts) >= 3:
                    lobby_name = parts[1]
                    player_name = ' '.join(parts[2:])
                    clientSocket.send(f'LEAVE_LOBBY {lobby_name} {player_name}'.encode())
                else:
                    print("Unknown command in lobby mode. Type 'help' for commands.")

    finally:
        try:
            clientSocket.close()
        except Exception:
            pass


if __name__ == '__main__':
    client_main()
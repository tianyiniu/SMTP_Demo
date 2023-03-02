import sys
import re
import os
from socket import *

ERROR_500 = "500 Syntax error: command unrecognized"
ERROR_501 = "501 Syntax error in parameters or arguments"
ERROR_503 = "503 Bad sequence of commands"
OK_250 = "250 OK"
OK_354 = "354 Start mail input; end with <CRLF>.<CRLF>"


class ParseError(Exception):
    """Responsible for reporting out-of-place characters in 501 errors."""

    def __init__(self, msg, char, pos, *args):
        self.msg = msg
        self.args = args
        self.char = char
        self.pos = pos

    def __str__(self):
        # return f"ERROR -- {self.msg} at pos {self.pos} next char {self.char}, ord {ord(self.char)}"
        return f"{self.msg}"
    

class SocketError(Exception):
    def __init__(self, msg="Error during socket operation"):
        self.msg = msg

    def __str__(self):
        return f"{self.msg}"
    

class EOFReceivedError(Exception):
    def __init__(self):
        self.msg = "EOF received on socket"
    
    def __str__(self):
        return f"{self.msg}"

class QUITError(Exception):
    "Closes connectionSocket when receiving QUIT command"
    def __init__(self, msg="Receiving QUIT command"):
        self.msg = msg
    
    def __str__(self):
        return f"{self.msg}"
    

class SyntaxError500(Exception):
    def __init__(self):
        self.msg = "500 Syntax error: command unrecognized"

    def __str__(self):
        return f"{self.msg}"


class SyntaxError501(Exception):
    def __init__(self):
        self.msg = "501 Syntax error in parameters or arguments"

    def __str__(self):
        return f"{self.msg}"


class OrderError503(Exception):
    def __init__(self):
        self.msg = "503 Bad sequence of commands"

    def __str__(self):
        return f"{self.msg}"


class HaltError(Exception):
    """Responsible for halting program if keyboard interrupt or EOF."""

    def __init__(self):
        self.msg = "No more lines to read or keyboard interrupt"

    def __str__(self):
        return f"{self.msg}"


class EOFInDATAError(Exception):
    """Error for handling EOF error in DATA command."""

    def __init__(self):
        self.msg = "EOF error in DATA command."

    def __str__(self):
        return f"{self.msg}"


class Parser():
    def __init__(self):
        self.sentence = None
        self.next_pos = -1
        self.next_char = None

    def flush(self):
        self.sentence = None
        self.next_pos = -1
        self.next_char = None

    def increment(self):
        self.next_pos += 1
        try:
            self.next_char = self.sentence[self.next_pos]
        except:
            self.next_char = None

    def parse_mail_from(self, sentence):
        self.sentence = sentence
        self.increment()
        try:
            self.mail_from_cmd()
            self.flush()
            return 250
        except SyntaxError500 as e:
            self.flush()
            return 500
        except SyntaxError501 as e:
            self.flush()
            return 501

    def parse_rcpt_to(self, sentence):
        self.sentence = sentence
        self.increment()
        try:
            self.rcpt_to_cmd()
            self.flush()
            return 250
        except SyntaxError500 as e:
            self.flush()
            return 500
        except SyntaxError501 as e:
            self.flush()
            return 501

    def parse_data(self, sentence):
        self.sentence = sentence
        self.increment()
        try:
            self.data_cmd()
            self.flush()
            return 354
        except SyntaxError500 as e:
            self.flush()
            return 500
        
    def parse_quit(self, sentence):
        self.sentence = sentence
        self.increment()
        try:
            self.quit_cmd()
            self.flush()
            return 250
        except SyntaxError500 as e:
            self.flush()
            return 500

    def parse_data_end(self, sentence):
        """Checks if sentence is data termination sequence."""
        self.sentence = sentence
        self.increment()
        try:
            self.data_end_cmd()
            self.flush()
            return True
        except SyntaxError500 as e:
            self.flush()
            return False
        
    def parse_helo(self, sentence):
        """Checks if sentence is helo command."""
        self.sentence = sentence
        self.increment()
        try:
            self.helo_cmd()
            self.flush()
            return 250
        except SyntaxError500 as e:
            self.flush()
            return 500
        except SyntaxError501 as e:
            self.flush()
            return 501

    def mail_from_cmd(self):
        if self.next_char != "M":
            raise SyntaxError500()
        self.increment()
        if self.next_char != "A":
            raise SyntaxError500()
        self.increment()
        if self.next_char != "I":
            raise SyntaxError500()
        self.increment()
        if self.next_char != "L":
            raise SyntaxError500()
        self.increment()

        try:
            self.whitespace()
        except ParseError:
            raise SyntaxError500()

        if self.next_char != "F":
            raise SyntaxError500()
        self.increment()
        if self.next_char != "R":
            raise SyntaxError500()
        self.increment()
        if self.next_char != "O":
            raise SyntaxError500()
        self.increment()
        if self.next_char != "M":
            raise SyntaxError500()
        self.increment()
        if self.next_char != ":":
            raise SyntaxError500()
        self.increment()

        try:
            self.nullspace()
            self.reverse_path()
            self.nullspace()
            self.crlf()
        except ParseError:
            raise SyntaxError501()

    def rcpt_to_cmd(self):
        if self.next_char != "R":
            raise SyntaxError500()
        self.increment()
        if self.next_char != "C":
            raise SyntaxError500()
        self.increment()
        if self.next_char != "P":
            raise SyntaxError500()
        self.increment()
        if self.next_char != "T":
            raise SyntaxError500()
        self.increment()

        try:
            self.whitespace()
        except ParseError:
            raise SyntaxError500()

        if self.next_char != "T":
            raise SyntaxError500()
        self.increment()
        if self.next_char != "O":
            raise SyntaxError500()
        self.increment()
        if self.next_char != ":":
            raise SyntaxError500()
        self.increment()

        try:
            self.nullspace()
            self.forward_path()
            self.nullspace()
            self.crlf()
        except ParseError:
            raise SyntaxError501()

    def data_cmd(self):
        if self.next_char != "D":
            raise SyntaxError500()
        self.increment()
        if self.next_char != "A":
            raise SyntaxError500()
        self.increment()
        if self.next_char != "T":
            raise SyntaxError500()
        self.increment()
        if self.next_char != "A":
            raise SyntaxError500()
        self.increment()

        try:
            self.nullspace()
            self.crlf()
        except ParseError:
            raise SyntaxError500()
        
    def quit_cmd(self):
        if self.next_char != "Q":
            raise SyntaxError500()
        self.increment()
        if self.next_char != "U":
            raise SyntaxError500()
        self.increment()
        if self.next_char != "I":
            raise SyntaxError500()
        self.increment()
        if self.next_char != "T":
            raise SyntaxError500()
        self.increment()

        try:
            self.nullspace()
            self.crlf()
        except ParseError:
            raise SyntaxError500()
        
    def helo_cmd(self):
        if self.next_char != "H":
            raise SyntaxError500()
        self.increment()
        if self.next_char != "E":
            raise SyntaxError500()
        self.increment()
        if self.next_char != "L":
            raise SyntaxError500()
        self.increment()
        if self.next_char != "O":
            raise SyntaxError500()
        self.increment()

        try:
            self.whitespace()
            self.domain()
            self.nullspace()
            self.crlf()
        except ParseError:
            raise SyntaxError501()

    def data_end_cmd(self):
        if self.next_char != ".":
            raise SyntaxError500()
        self.increment()

        try:
            self.crlf()
        except ParseError:
            raise SyntaxError500()

    def whitespace(self):
        try:
            self.sp()
        except ParseError:
            raise ParseError(msg="whitespace", pos=self.next_pos, char=self.next_char)

        try:
            self.whitespace()
        except ParseError:
            pass

    def sp(self):
        if self.next_char == " " or self.next_char == "\t":
            self.increment()
        else:
            raise ParseError(msg="sp", pos=self.next_pos, char=self.next_char)

    def nullspace(self):
        self.null()
        try:
            self.whitespace()
        except ParseError:
            pass

    def null(self):
        return

    def reverse_path(self):
        self.path()

    def forward_path(self):
        self.path()

    def path(self):
        if self.next_char != "<":
            raise ParseError(msg="path", pos=self.next_pos, char=self.next_char)
        self.increment()

        self.mailbox()

        if self.next_char != ">":
            raise ParseError(msg="path", pos=self.next_pos, char=self.next_char)
        self.increment()

    def mailbox(self):
        self.local_part()

        if self.next_char != "@":
            raise ParseError(msg="mailbox", pos=self.next_pos, char=self.next_char)
        self.increment()

        self.domain()

    def local_part(self):
        self.string()

    def string(self):
        try:
            self.char()
        except ParseError:
            raise ParseError(msg="string", pos=self.next_pos, char=self.next_char)

        try:
            self.string()
        except ParseError:
            pass

    def char(self):
        EXCLUDED_ASCII = [60, 62, 40, 41, 91, 93, 92, 46, 44, 59, 58, 64, 34, 32, 9]
        ascii_num = ord(self.next_char)
        if 32 <= ascii_num and ascii_num <= 126 and ascii_num not in EXCLUDED_ASCII:
            self.increment()
        else:
            raise ParseError(msg="char", pos=self.next_pos, char=self.next_char)

    def domain(self):
        self.element()

        if self.next_char == ".":
            self.increment()
            self.domain()

    def element(self):
        try:
            self.letter()
        except ParseError:
            raise ParseError(msg="element", pos=self.next_pos, char=self.next_char)

        try:
            self.let_dig_str()
        except ParseError:
            pass

    def name(self):
        try:
            self.letter()
        except ParseError:
            raise ParseError(msg="name", pos=self.next_pos, char=self.next_char)

        self.let_dig_str()

    def letter(self):
        if self.next_char.isalpha() or self.next_char.isdigit():
            self.increment()
        else:
            raise ParseError(msg="letter", pos=self.next_pos, char=self.next_char)

    def let_dig_str(self):
        self.let_dig()

        try:
            self.let_dig_str()
        except ParseError:
            pass

    def let_dig(self):
        try:
            self.letter()
        except ParseError:
            try:
                self.digit()
            except ParseError:
                raise ParseError(msg="let-dig", pos=self.next_pos, char=self.next_char)

    def digit(self):
        if self.next_char.isdigit():
            self.increment()
        else:
            raise ParseError(msg="digit", char=self.next_char, pos=self.next_pos)

    def crlf(self):
        if self.next_char == "\n" or self.next_char == "\r":
            self.increment()
        else:
            raise ParseError(msg="CRLF", char=self.next_char, pos=self.next_pos)

    def special(self):
        if self.next_char in '<>()[]\\.,;:@"':
            self.increment()
        else:
            raise ParseError(msg="special", char=self.next_char, pos=self.next_pos)


class Server():
    def __init__(self, port):
        self.parser = Parser()
        self.EMAIL_REGEX = "<.+>"
        self.serverPort = int(port)
        self.hostname = gethostname()
        self.received_text = None
        self.curr_index = 0

        self.text = []
        self.forward_domains = []
        self.sentence = None

    def reset(self):
        self.received_text = None
        self.curr_index = 0
        self.text = []
        self.forward_domains = []
        self.sentence = None

    def extract_domain(self):
        """Extracts domain from RCPT to command"""
        match = re.search(self.EMAIL_REGEX, self.sentence)
        domain = match.group().strip("<").strip(">").split("@")[-1]
        return domain

    def write_to_files(self):
        for domain in self.forward_domains:
            file_name = domain.strip("\n")
            with open(f"{os.path.dirname(os.path.realpath(__file__))}/forward/{file_name}", "a") as f:
                f.writelines(self.text)

    def which_cmd(self, sentence=None):
        """Determines if .sentence is a valid cmd, and if syntax correct."""
        if not sentence:
            sentence = self.sentence

        cmd = None
        syntax_correct = None

        mail_from_code = self.parser.parse_mail_from(sentence)
        rcpt_to_code = self.parser.parse_rcpt_to(sentence)
        data_code = self.parser.parse_data(sentence)
        helo_code = self.parser.parse_helo(sentence)
        quit_code = self.parser.parse_quit(sentence)

        if mail_from_code == 250 or mail_from_code == 501:
            cmd = "mail_from"
            syntax_correct = False if mail_from_code == 501 else True
        elif rcpt_to_code == 250 or rcpt_to_code == 501:
            cmd = "rcpt_to"
            syntax_correct = False if rcpt_to_code == 501 else True
        elif data_code == 354 or data_code == 501:
            cmd = "data"
            syntax_correct = False if data_code == 501 else True
        elif quit_code == 250 or quit_code == 501:
            cmd = "quit"
            syntax_correct == False if quit_code == 501 else True
        elif helo_code == 250 or helo_code == 501:
            cmd = "helo"
            syntax_correct = False if helo_code == 501 else True
        else:
            raise SyntaxError500()  # Invalid command
        return (cmd, syntax_correct)
    
    def socket_read(self, socket):
        try:
            sentence = socket.recv(2048)
            #print(f"Just read: {[sentence.decode()]}")
            if sentence.decode() == '':
                raise HaltError()
            return sentence.decode()
        except Exception as e:
            print(e)
            raise SocketError(msg="Error reading socket")
        
    def socket_write(self, socket, line):
        #print(f"Trying to write: {[line]}")
        try:
            sentence = line.encode()
            socket.sendall(sentence)
        except Exception:
            raise SocketError(msg=f"Socket error when writing: {line}")

    def read_sentence(self, connection_socket, in_data=False):
        """Reads a single sentence from socket and assigns to .sentence field."""
        try:
            self.sentence = self.socket_read(connection_socket)
            if self.sentence == '':
                if not in_data:
                    raise HaltError()
                else:
                    raise EOFInDATAError()
        except KeyboardInterrupt:
            raise HaltError()
        except (EOFError, SystemExit):
            if not in_data:
                raise HaltError()
            else:
                raise EOFInDATAError()
    
    def get_next(self):
        try:
            self.sentence = self.received_text[self.curr_index]
            self.curr_index += 1
        except IndexError:
            raise SocketError("Get_next index incorrect")


    def get_email(self, connectionSocket):
        self.reset() # Ensure previouos data has been erased

        while True:
            try:  # Program halts if keyboard interrupt or reaches end of file
                try:
                    self.reset()
                    # Get email
                    self.read_sentence(connectionSocket)
                    self.received_text = self.sentence.split("\n")
                    if (self.received_text[-1] == ""):
                        self.received_text.pop()
                    self.received_text = [line + "\n" for line in self.received_text]

                    # Check if is mail from
                    self.get_next()
                    cmd, syntax_correct = self.which_cmd()  # Will raise 500 error is cmd invalid
                    if cmd == "quit":
                        raise QUITError()
                    elif cmd != "mail_from":
                        raise OrderError503()
                    elif syntax_correct == False:
                        raise SyntaxError501()
                    
                    # Check if is rcpt to
                    self.get_next()
                    cmd, syntax_correct = self.which_cmd()  # Will raise 500 error is cmd invalid
                    if cmd == "quit":
                        raise QUITError()
                    elif cmd != "rcpt_to":
                        raise OrderError503()
                    elif syntax_correct == False:
                        raise SyntaxError501()

                    # Append domain to self.domains if not already there
                    rcpt_domain = self.extract_domain()
                    if rcpt_domain not in self.forward_domains:
                        self.forward_domains.append(rcpt_domain)


                    # While loop to read and assign any further recipients
                    while cmd == "rcpt_to":
                        self.get_next()
                        cmd, syntax_correct = self.which_cmd()
                        if cmd == "quit":
                            raise QUITError()
                        elif cmd == "data":
                            break
                        elif cmd == "mail_from" or cmd == "helo":
                            raise OrderError503()
                        elif syntax_correct == False:  # if reached, cmd must be "rcpt_to"
                            raise SyntaxError501()
                        else:
                            rcpt_domain = self.extract_domain()
                            if rcpt_domain not in self.forward_domains:
                                self.forward_domains.append(rcpt_domain)

                    # NOTE: no need to read another sentence because while loop 
                    # NOTE: also, cmd must be data due to "break" in while loop
                    # While loop to read all lines, append to .text, until data termination
                    # current, .sentence is still the "DATA" command
                    try:
                        self.get_next()
                        while not self.parser.parse_data_end(self.sentence):
                            self.text.append(self.sentence)
                            self.get_next()
                        self.socket_write(connectionSocket, OK_250)
                    except EOFInDATAError:
                        raise SyntaxError501()

                    # Write text to appropiate forward paths
                    self.write_to_files()

                except SyntaxError500:
                    self.socket_write(connectionSocket, ERROR_500)
                    self.reset()
                    continue
                except OrderError503 as e:
                    self.socket_write(connectionSocket, ERROR_503)
                    self.reset()
                    continue
                except SyntaxError501 as e:
                    self.socket_write(connectionSocket, ERROR_501)
                    self.reset()
                    continue
                except QUITError:
                    self.socket_write(connectionSocket, f"221 {self.hostname} closing connection")
                    connectionSocket.close()
                    return
            except HaltError as e:
                connectionSocket.close()
                return
            except SocketError as e:
                print(f"ERROR - {e}")
                connectionSocket.close()
                return

    def run_server(self):
        """Server's main loop."""

        # Create connection socket
        try:
            serverSocket = socket(AF_INET, SOCK_STREAM)
            serverSocket.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
            serverSocket.bind(("", self.serverPort))
            serverSocket.listen(1)
        except Exception as e:
            print(e)
            print("ERROR - Cannot establish welcome socket")
            return
        
        # This while loop should never terminate 
        while True:
            connectionSocket = None
            try:
                connectionSocket, addr = serverSocket.accept()
            except Exception:
                print("ERROR - Error when establishing connection socket")
                continue

            # Send greeting message
            try:
                serverGreeting = f"220 {self.hostname}"
                self.socket_write(connectionSocket, serverGreeting)
            except SocketError:
                print(msg="ERROR - cannot send greeting to client")
                connectionSocket.close()
                continue

            handshake_established = False
            while not handshake_established:
                try:
                    # Send greeting message
                    client_greeting = self.socket_read(connectionSocket)
                    cmd, syntax_correct = self.which_cmd(client_greeting)
                    if cmd == "quit":
                        raise QUITError()
                    elif cmd != "helo":
                        self.socket_write(connectionSocket, ERROR_503)
                    elif syntax_correct == False:
                        self.socket_write(connectionSocket, ERROR_501)
                    else:
                        handshake_established = True
                        client_name = client_greeting.strip("\n").strip(" ").strip("HELO").strip(" ")
                        greeting_message = f"250 Hello {client_name} pleased to meet you"
                        self.socket_write(connectionSocket, greeting_message)

                except SocketError:
                    print("ERROR - handshake failed")
                    connectionSocket.close()
                    break
                except SyntaxError500:
                    try:
                        self.socket_write(connectionSocket, ERROR_500)
                        continue
                    except SocketError:
                        print("ERROR - Cannot write 500 to greeting message")
                        connectionSocket.close()
                        break
                except QUITError:
                    try:
                        self.socket_write(connectionSocket, f"221 {self.hostname} closing connection")
                        connectionSocket.close()
                        break
                    except SocketError:
                        print("ERROR - Cannot write 221 quit message")
                        connectionSocket.close()
                        break

            if handshake_established:
                # Reads mail
                self.get_email(connectionSocket)


if __name__ == "__main__":
    port = sys.argv[1]
    try:
        port = int(port)
    except Exception:
        print("Port is not a number")

    aserver = Server(port=port)
    aserver.run_server()

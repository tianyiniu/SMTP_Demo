import sys
import os
import re
import time
from socket import *

import email
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage


EMAIL_REGEX = "<.+>"
WAIT_TIME = 0.05

class QuitError(Exception):
    def __init__(self, error_response=None, msg=None):
        if msg:
            self.msg = "QUIT EMITTED"
        else:
            self.msg = f"QUIT EMITTED when {msg}"
        self.error_response = error_response

    def __str__(self):
        return f"{self.error_response} {self.msg}"

    def has_error(self):
        return True if self.error_response else False
    

class SocketError(Exception):
    def __init__(self, msg="Error during socket operation"):
        self.msg = msg
    
    def __str__(self):
        return f"{self.msg}"


class FileEndError(Exception):
    def __init__(self):
        self.msg = f"EOF reached"

    def __str__(self):
        return self.msg


class ParseError(Exception):
    def __init__(self, msg, char, pos, *args):
        self.msg = msg
        self.args = args
        self.char = char
        self.pos = pos

    def __str__(self):
        #return f"ERROR -- {self.msg} at pos {self.pos} next char {self.char}, ord {ord(self.char)}"
        return f"ERROR -- {self.msg}"


class Parser:
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
    
    def parse_mailbox(self, sentence):
        self.sentence = sentence
        self.increment()
        try:
            self.nullspace()
            self.mailbox()
            self.nullspace()
            self.crlf()
            self.flush()
            return True
        except ParseError as e:
            self.flush()
            print(e)
            return False
        
    def parse_domain(self, sentence):
        self.sentence = sentence
        self.increment()
        try:
            self.domain()
            self.nullspace()
            self.crlf()
            self.flush()
            return True
        except ParseError as e:
            self.flush()
            return False

    def mail_from_cmd(self):
        if self.next_char != "M":
            raise ParseError(msg="mail-from-cmd", pos=self.next_pos, char=self.next_char)
        self.increment()
        if self.next_char != "A":
            raise ParseError(msg="mail-from-cmd", pos=self.next_pos, char=self.next_char)
        self.increment()
        if self.next_char != "I":
            raise ParseError(msg="mail-from-cmd", pos=self.next_pos, char=self.next_char)
        self.increment()
        if self.next_char != "L":
            raise ParseError(msg="mail-from-cmd", pos=self.next_pos, char=self.next_char)
        self.increment()

        self.whitespace()

        if self.next_char != "F":
            raise ParseError(msg="mail-from-cmd", pos=self.next_pos, char=self.next_char)
        self.increment()
        if self.next_char != "R":
            raise ParseError(msg="mail-from-cmd", pos=self.next_pos, char=self.next_char)
        self.increment()
        if self.next_char != "O":
            raise ParseError(msg="mail-from-cmd", pos=self.next_pos, char=self.next_char)
        self.increment()
        if self.next_char != "M":
            raise ParseError(msg="mail-from-cmd", pos=self.next_pos, char=self.next_char)
        self.increment()
        if self.next_char != ":":
            raise ParseError(msg="mail-from-cmd", pos=self.next_pos, char=self.next_char)
        self.increment()

        self.nullspace()
        self.reverse_path()
        self.nullspace()
        self.crlf()

    def rcpt_to_cmd(self):
        if self.next_char != "R":
            raise ParseError(msg="rcpt-to-cmd", pos=self.next_pos, char=self.next_char)
        self.increment()
        if self.next_char != "C":
            raise ParseError(msg="rcpt-to-cmd", pos=self.next_pos, char=self.next_char)
        self.increment()
        if self.next_char != "P":
            raise ParseError(msg="rcpt-to-cmd", pos=self.next_pos, char=self.next_char)
        self.increment()
        if self.next_char != "T":
            raise ParseError(msg="rcpt-to-cmd", pos=self.next_pos, char=self.next_char)
        self.increment()

        self.whitespace()

        if self.next_char != "T":
            raise ParseError(msg="rcpt-to-cmd", pos=self.next_pos, char=self.next_char)
        self.increment()
        if self.next_char != "O":
            raise ParseError(msg="rcpt-to-cmd", pos=self.next_pos, char=self.next_char)
        self.increment()
        if self.next_char != ":":
            raise ParseError(msg="rcpt-to-cmd", pos=self.next_pos, char=self.next_char)
        self.increment()

        self.nullspace()
        self.forward_path()
        self.nullspace()
        self.crlf()

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
        if self.next_char.isalpha():
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


class Client:
    def __init__(self, serverName, port=None, check_arguments=True):
        self.serverName = serverName
        self.port = port
        self.myName = gethostname()
        self.WD = os.path.dirname(os.path.realpath(__file__))
        self.parser = Parser()
        self.check_arguments = check_arguments

        # Stores information for an email
        self.from_field = None
        self.to_field = []
        self.subject_field = None
        self.message_field = []
        self.msg = ""
        self.attachment_path = ""

    def extract_email(self, line):
        """Extracts email address from string."""
        match = re.search(EMAIL_REGEX, line)
        return match.group()

    def extract_response_code(self, response):
        """Extracts response code from SMTP server"""
        try: 
            code = int(response[0:3])
        except Exception:
            code = 600
        return code

    def is_error_code(self, code, expected=None):
        """Returns whether a response code is an error code."""
        if expected:
            return False if code in expected else True
        return True if code//100 == 5 else False
    
    def check_response(self, response, expected=None):
        """Checks if server response is an error, QUIT if so."""
        is_error = self.is_error_code(self.extract_response_code(response), expected)
        if is_error:
            raise QuitError()
        return
    
    def socket_write(self, socket, line):
        #print(f"Trying to write: {[line]}")
        try:
            sentence = line.encode()
            socket.sendall(sentence)
        except Exception:
            raise SocketError(msg=f"Socket error when writing: {line}")
    
    def socket_read(self, socket):
        try:
            sentence = socket.recv(2048)
            #print(f"Just read: {[sentence.decode()]}")
            return sentence.decode()
        except Exception:
            raise SocketError(msg="Error reading socket")

    def get_email(self):
        """CLI interface for reading user email."""

        # Get "from"
        sys.stdout.write("From:\n")
        from_field = sys.stdin.readline()
        print(from_field) # TODO
        while not self.parser.parse_mailbox(from_field):
            sys.stdout.write("From:\n")
            from_field = sys.stdin.readline()
            if from_field == "":
                raise FileEndError()
        from_field = "<" + from_field.strip("\n").strip(" ") + ">"
        self.from_field = from_field + "\n"

        # Get "to", may be a list of recipients
        while True:
            RCPTS = True
            sys.stdout.write("To:\n")
            to_field = sys.stdin.readline()
            if to_field == "":
                raise FileEndError()
            print(to_field) #TODO
            emails = to_field.split(",")
            for email in emails:
                email = email.strip(" ") + "\n"
                if not self.parser.parse_mailbox(email):
                    RCPTS = False
                    break
                email = "<" + email.strip(" ").strip("\n") + ">"
                self.to_field.append(email + "\n")
            if RCPTS:
                break

        # Get message subject
        sys.stdout.write("Subject:\n")
        self.subject_field = sys.stdin.readline()
        if self.subject_field == "":
            raise FileEndError()
        print(self.subject_field) # TODO

        # Get message
        sys.stdout.write("Message:\n")
        while True:
            line = sys.stdin.readline()
            print([line]) # TODO
            if line == "":
                raise FileEndError()
            elif line == ".\n":
                break
            self.message_field.append(line)

        # Get attachment
        sys.stdout.write("Attachment:\n")
        self.attachment_path = sys.stdin.readline()        
        
    def send_email(self):
        """Sends email to server."""
        clientSocket = None
        try:
            try:
                clientSocket = socket(AF_INET, SOCK_STREAM)
                #clientSocket.setsockopt(IPPROTO_TCP, TCP_NODELAY, 1)
                clientSocket.connect((self.serverName, int(self.port)))
            except Exception as e:
                print(e)
                raise SocketError(msg="Error during clientSocket creation")
        
            # HELO
            server_greeting = self.socket_read(clientSocket)
            self.check_response(server_greeting, expected=[220])

            self.socket_write(clientSocket, f"HELO {self.myName}\n")
            server_helo_response = self.socket_read(clientSocket)
            self.check_response(server_helo_response, expected=[250])

            # MAIL FROM
            self.msg += f"MAIL FROM: {self.from_field}"

            # RCPT TO
            for rcpt in self.to_field:
                self.msg += f"RCPT TO: {rcpt}"

            # DATA command
            data = "DATA\n"
            self.msg += data

            # Start composing MIME message
            message = MIMEMultipart()
            message["From"] = self.from_field
            message["To"] = ", ".join(self.to_field).replace("\n", "") + "\n"
            message["Subject"] = self.subject_field
            
            # Add message body
            body = "".join(self.message_field)
            message.attach(MIMEText(body, "plain"))

            # Get and add attachment image
            filename = self.attachment_path
            if filename[-1] == "\n":
                filename = filename.strip("\n")
            with open(filename, "rb") as img:
                msgImage = MIMEImage(img.read(), _subtype="png")
            message.attach(msgImage)

            self.msg += message.as_string()

            # Write terminaiton dot
            self.msg += ".\n"

            # Write message
            self.socket_write(clientSocket, self.msg)
            server_email_response = self.socket_read(clientSocket)
            self.check_response(server_email_response)

            # QUIT, raise QUITError handling emitting and receiving QUIT command
            raise QuitError()

        except SocketError as se:
            clientSocket.close()
            print(se)
            return
        except QuitError:
            try:
                self.socket_write(clientSocket, "QUIT\n")
                server_quit_response = self.socket_read(clientSocket)
                self.check_response(server_quit_response, expected=[221])
                clientSocket.close()
                return
            except SocketError:
                #print("ERROR - Error in socket operation when emitting QUIT")
                clientSocket.close()
                return
            except QuitError:
                #print("ERROR - Server did not successfully acknowledge QUIT")
                clientSocket.close()
                return


    def start_client(self):
        # Checks if domain name is valid
        # if self.check_arguments and not self.parser.parse_domain(self.serverName+"\n"):
        #     sys.stdout.write("ERROR - domain name invalid\n")
        #     return
    
        # Checks if port number is valid
        if self.check_arguments and not self.port.isdigit():
            sys.stdout.write("ERROR - port number invalid\n")
            return
        self.port = int(self.port)

        try:
            self.get_email()
        except KeyboardInterrupt:
            return
        except FileEndError as e:
            print(e)
            return
        
        self.send_email()


if __name__ == "__main__":
    serverName = sys.argv[1]
    port = sys.argv[2]
    aClient = Client(serverName, port)
    aClient.start_client()

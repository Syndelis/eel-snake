"""
Imports
"""

# Engine imports
from eel import Eel, keyPressed, Canvas, mousePressed, getText
from figure import Rectangle, Line, Font, Circle
from shader import Shader

# General imports
from random import randint
from typing import Iterable
from enum import Enum

# Multiplayer imports
import socket
from threading import Thread
from pickle import dumps, loads
from time import sleep
from json import load as json_load
from ctypes import c_uint64
# ------------------------------------------------------------------------------
"""
Global constants
"""
# Window stuff
WIDTH, HEIGHT = 640, 480
SQ = 32
VSYNC = True

# Multiplayer
PORT = 7777
MAXPLAYERS = 8

# Debug
FORCEDEFAULTCONN = True

# Game state
class GameState(Enum):

    MENU=0
    SINGLEPLAYER=1
    HOST=2
    CLIENT=3

# ------------------------------------------------------------------------------
"""
Class definitions
"""
class Vector(tuple):

    table = {'x': 0, 'y': 1}

    def __add__(self, other):
        tmp = self[0] + other[0], self[1] + other[1]
        return type(other)(tmp)


    def __sub__(self, other):
        tmp = self[0] - other[0], self[1] - other[1]
        return type(other)(tmp)


    def __mul__(self, other):

        if isinstance(other, int) or isinstance(other, float):
            return Vector((self[0] * other, self[1] * other))

        elif isinstance(other, Iterable):
            return type(other)(self[0] * other[0], self[1] * other[1])

        else: raise TypeError(
            f"Unsupported type for Vector.__mul__ `{type(other)}`")


    def __div__(self, other):

        if isinstance(other, int) or isinstance(other, float):
            return Vector((self[0] / other, self[0] / other))

        elif isinstance(other, Iterable):
            return type(other)(self[0] / other[0], self[1] / other[1])

        else: raise TypeError(
            f"Unsupported type for Vector.__mul__ `{type(other)}`")


    def __neg__(self):
        return self * (-1)


    def __getattribute__(self, name):
        if name in Vector.table: return self[Vector.table[name]]
        return super().__getattribute__(name)


UP    = Vector(( 0, -1))
DOWN  = Vector(( 0,  1))
RIGHT = Vector(( 1,  0))
LEFT  = Vector((-1,  0))

class Snake:

    def __init__(self, x, y, size=3, body_dir=RIGHT):

        initial_pos = Vector((x, y)) * SQ - Vector((0, SQ/2))

        self.body = [
            Rectangle(
                *(initial_pos + body_dir * (SQ * i)),
                width=SQ, height=SQ, fill=True
            ) for i in range(size)
        ]

        self.color = (randint(50, 255), randint(50, 255), randint(50, 255))
        for i in self.body:
            i.setColor(*self.color)

        self.dir = body_dir * -1
        self.olddir = self.dir
        self.controls = None


    def grow(self):
        self.body.append(None)


    def setColor(self, r, g, b):
        self.color = (r, g, b)
        for i in self.body: i.setColor(*self.color)


    def step(self, minv, maxv, others=None) -> bool:
        "Returns wether the player is dead or not"

        self.olddir = self.dir
        nextpos = (self.dir * SQ) + self.head.pos

        # Collision with arena boundaries
        for i, v in enumerate(nextpos):
            if v < minv[i] or v > maxv[i]:
                return True

        # Collision with other body parts
        for i in range(1, len(self.body)):
            v = self.body[i]
            if v and nextpos == v.pos:
                return True

        # Collision with other snakes
        if isinstance(others, Iterable):
            for snake in others:
                if snake is not self:
                    for bodypart in snake:
                        if bodypart and nextpos == bodypart.pos:
                            return True

        # Move body parts
        for i in range(1, len(self.body))[::-1]:

            v = self.body[i]
            if v:
                v.pos = self.body[i-1].pos

            else:
                v = self.body[i-1]
                self.body[i] = Rectangle(
                    v.x, v.y, width=SQ, height=SQ, fill=True
                )
                self.body[i].setColor(*self.color)

        self.body[0].pos = tuple(nextpos)

        return False


    def setScheme(self, **kwargs):
        # Input type should be `up=..., down=..., right=..., left=...`
        self.controls = {
            kwargs['up'   ]: UP,
            kwargs['down' ]: DOWN,
            kwargs['left' ]: LEFT,
            kwargs['right']: RIGHT,
        }


    def sendInput(self, inp):

        pot = self.controls[inp]
        if not (pot == -self.olddir):
            self.dir = pot


    def drawTo(self, target):

        for i in self.body:
            if i: i.drawTo(target)


    def getHead(self):
        return self.body[0]


    def getTail(self):
        return self.body[-1]


    def __len__(self):
        return len(self.body)


    def __iter__(self):
        return iter(self.body)


    head = property(getHead)
    tail = property(getTail)
# ------------------------------------------------------------------------------
"""
Game state
"""

menu_str = (
    b"Singleplayer",
    b"Multiplayer - Host",
    b"Multiplayer - Join"
)

global menu, font
font = None
menu = []
# menu = [
#     (
#         Rectangle(20 - 10, 100 + 60*i - 40, width=600, height=50, fill=True),
#         font.text(20, 100 + 60*i, v)# Text(20, 100 + 60*i, text=v, font=b"Ubuntu-R.ttf")
#     ) for i, v in enumerate(menu_str)
# ]

# for item in menu:
#     item[0].setColor(20, 20, 20)

menu_rect = Rectangle(0, 0, width=600, height=50)
menu_rect.setColor(150, 150, 30)

menu_mouse = Circle(0, 0, radius=10)


def gameMenu(eel):
    global current_state

    for item in menu:
        for shape in item:
            shape.drawTo(canvases[0])

    menu_mouse.pos = eel.mouse
    for i, item in enumerate(menu):
        if menu_mouse.collidesWith(item[0]):

            menu_rect.pos = item[0].pos
            menu_rect.drawTo(canvases[0])

            if mousePressed(0): current_state = GameState(i+1)

            break


global timer, maxtimer
maxtimer = 4
timer = maxtimer

global player, apple
player = None
apple = None

minv = Vector((0, 0))
maxv = Vector((WIDTH-SQ, HEIGHT-SQ))

lines = []
for y in range(0, HEIGHT, SQ):
    l = Line(0, y, xp=WIDTH, yp=y)
    l.setColor(50, 50, 50, 50)
    lines.append(l)

for x in range(0, WIDTH, SQ):
    l = Line(x, 0, xp=x, yp=HEIGHT)
    l.setColor(50, 50, 50, 50)
    lines.append(l)


def gameRandomApple(snakes):
    global apple

    coincide = True

    while coincide:
        apple.pos = (randint(0, WIDTH/SQ-1) * SQ, randint(0, HEIGHT/SQ-1) * SQ)

        coincide = False
        for snake in snakes:
            for body in snake:
                if body and body.pos == apple.pos: coincide = True


def gameSingSetup(eel):
    global setup, player, apple

    player = Snake(WIDTH/SQ / 2, HEIGHT/SQ / 2)
    player.setScheme(up=b'W', down=b'S', left=b'A', right=b'D')

    apple = Rectangle(
        randint(0, WIDTH/SQ-1) * SQ, randint(0, HEIGHT/SQ-1) * SQ,
        width=SQ, height=SQ, fill=True
    )
    apple.setColor(200, 0, 0)

    setup = True


def gameSing(eel):
    global timer, maxtimer, setup, player, apple
    if not setup: gameSingSetup(eel)

    if keyPressed(256): exit()
    if keyPressed(b'R'): setup = False

    timer -= 1
    if timer <= 0:
        for k in player.controls:
            if keyPressed(k): player.sendInput(k)

        player.step(minv, maxv)
        if player.head.pos == apple.pos:
            player.grow()
            gameRandomApple([player])

        timer = maxtimer

    player.drawTo(canvases[0])
    apple.drawTo(canvases[0])


global sock
sock = None

global players, player_list
players = None
player_list = None

global listen_thread
listen_thread = None

global input_thread
input_thread = None

global clients
clients = None


def getPickle():
    global player_list, apple
    return dumps(player_list + [apple.pos])


def gameHostListen():
    global sock, players, clients, player_list

    while True:

        print('thread running')

        conn, addr = sock.accept()
        print(f'New connection from {addr}')

        clients.append(conn)
        conn.send(getPickle())
        print("Sent a pickle to the new connection")

        player_list.append([])
        players.append(
            Snake(WIDTH/SQ, randint(0, HEIGHT/SQ - 1) - .5)
        )
        print(f"New snake at ({players[-1].head.pos})")
        players[-1].setScheme(up=b'W', down=b'S', left=b'A', right=b'D')

        for body in players[-1]:
            player_list[-1].append(body.pos)


def gameHostInput():
    global sock, clients, players

    while True:
        for i, client in enumerate(clients):
            inp = client.recv(1)
            if inp: players[i].sendInput(inp)


def gameHostSetup():
    global sock, players, listen_thread, setup, apple, clients, player_list
    global input_thread

    print('Host setup')

    sock = socket.socket()
    sock.bind(('', PORT))
    sock.listen(MAXPLAYERS)

    setup = True
    players = []
    player_list = []
    clients = []

    apple = Rectangle(
        randint(0, WIDTH/SQ-1) * SQ, randint(0, HEIGHT/SQ-1) * SQ,
        width=SQ, height=SQ, fill=True
    )
    apple.setColor(200, 0, 0)

    listen_thread = Thread(target=gameHostListen)
    listen_thread.daemon = True
    listen_thread.start()

    input_thread = Thread(target=gameHostInput)
    input_thread.daemon = True
    input_thread.start()


def gameHost(eel):
    global sock, setup, timer, maxtimer, apple, players, clients, player_list
    if not setup:
        gameHostSetup()
        # eel.close()

    # print("Processing timer")

    timer -= 1
    if timer <= 0:

        # print("Update time")

        for i, p in enumerate(players):

            p.step(minv, maxv, others=players)
            if p.head.pos == apple.pos:
                p.grow()
                gameRandomApple(players)

            player_list[i] = []
            for body in p:
                if body:
                    player_list[i].append(body.pos)

        timer = maxtimer

    # print("Sending data to peers")

    d = getPickle()
    for client in clients:
        client.send(d)

    # print("All data sent")


def fromPickle(pick):
    global players, apple

    # print(pick)

    # if len(pick)-1 > len(players):
    #     players.append(Snake(*pick[-2][0], size=len(pick[-2])))

    # if len(pick) > 1:
    #     for i, player in enumerate(players):
            # for j, body in enumerate(player): body.pos = pick[i][j]

    l = len(players)
    for i, snake in enumerate(pick[:-1]):

        if i >= l: players.append(Snake(0, 0, size=len(snake)))

        p = players[i]
        
        while len(snake) > len(p): p.grow()

        for j, body in enumerate(p):
            if body:
                body.pos = snake[j]

            else:
                p.body[j] = Rectangle(
                    *snake[j], width=SQ, height=SQ, fill=True)

                p.body[j].setColor(*p.color)            


    if len(pick) and len(players): apple.pos = pick[-1]


default_connection = {
    "host": "",
    "port": 7777,
    "direct": ""
}

global iptext
iptext = None

def gameClientSetup():
    global sock, setup, players, apple

    config = default_connection

    try:
        assert not FORCEDEFAULTCONN
        with open("connection.json", "r") as f:
            config = json_load(f)

    except: pass

    iptext.text = b''

    sock = socket.socket()
    try:
        sock.connect((config["host"], config["port"]))

    except (socket.gaierror, socket.error, ConnectionRefusedError):
        try:
            sock.connect((config["direct"], config["port"]))

        except:
            print("Can't establish connection with host.")
            exit(1)

    # sock.connect(('', PORT))
    

    apple = Rectangle(0, 0, width=SQ, height=SQ, fill=True)
    apple.setColor(200, 0, 0)

    print("Connection established. Receiving first pickle...")

    p = loads(sock.recv(4096))

    print("Package received and unpickled. Interpreting it...")
    # print(p)
    # print([len(pl) for pl in p])
    players = [Snake(0, 0, size=len(pl)) for pl in p]

    fromPickle(p)

    print("Package interpreted successfully. Setup is complete")

    setup = True


inp = [b'W', b'A', b'S', b'D']

def gameClient(eel):
    global setup, players, sock, apple
    if not setup: gameClientSetup()

    # print("Ready to read input and send to masterserver")
    sent = False

    for i in inp:
        if keyPressed(i):
            sent = True
            sock.send(i)
            break

    if not sent: sock.send(b'')
    # print("Input successfully sent. Now waiting for response...")

    # test this bad boy
    data = sock.recv(4096)
    # print(data)

    # print("Response arrived. Time for unpickling and interpretation...")
    # print(data)
    fromPickle(loads(data))
    # fromPickle(loads(sock.recv(4096)))

    for player in players: player.drawTo(canvases[0])
    apple.drawTo(canvases[0])

# ------------------------------------------------------------------------------
"""
Game loop
"""

game = Eel(name="Snake", width=WIDTH, height=HEIGHT, vsync=VSYNC)
game_phases = (gameMenu, gameSing, gameHost, gameClient)

# State
global current_state, setup
current_state = -1
setup = False

# Shader+Canvas
global shaders, canvases
shadernames = (b'crt.frag', b'chroma.frag', b'vignette.frag')
shaders = None
canvases = None

@game.load
def gameLoad(eel):
    global current_state, setup, shaders, canvases, font, iptext

    current_state = GameState.MENU
    setup = False

    if shaders is None:
        shaders = []
        for frag in shadernames:

            sh = Shader(b'pass.vert', frag)
            with sh:
                sh.setUniform(b'canvasTexture', (0,))
                sh.setUniform(b'resolution', eel.dimensions)
                shaders.append(sh)

    if canvases is None:
        canvases = [Canvas(*eel.dimensions) for i in range(2)]

    
    if font is None:

        font = Font("Ubuntu-R.ttf")

        for i, v in enumerate(menu_str):
            menu.append((
                Rectangle(20 - 10, 100 + 60*i - 40, width=600, height=50, fill=True),
                font.text(20, 100 + 60*i, v)
            ))

        for item in menu:
            item[0].setColor(20, 20, 20)

        iptext = font.text(20, 160, b'')


@game.draw
def mainLoop(eel):
    global current_state

    # Still waiting for Python 3.10's `match` statement
    game_phases[current_state.value](eel)

@game.draw
def applyShader(eel):
    global current_state

    for l in lines: l.drawTo(canvases[0])

    for i, sh in enumerate(shaders):
        with sh:
            c = i&1
            canvases[c].drawTo(canvases[1-c])

    c = (i+1)&1
    canvases[c].drawTo(eel)
    for c in canvases: c.clear()


game.run()
if listen_thread is not None:pass

# while current_state is GameState.HOST:
#     gameHost(None)

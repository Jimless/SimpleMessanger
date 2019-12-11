import re
from time import gmtime, strftime

from twisted.internet import reactor
from twisted.internet.address import IPv4Address
from twisted.internet.protocol import ServerFactory, connectionDone
from twisted.protocols.basic import LineOnlyReceiver

from Helpers import make_printable


class ServerProtocol(LineOnlyReceiver):
    factory: 'Server'
    login: str = None
    _peer: IPv4Address
    __terminate_later: object

    def __terminate(self, message=None):
        """ abort connection """
        self.__terminate_later = None
        if message is not None:
            self.send_message(message)
        self.transport.loseConnection()

    def __cancel_login_timeout(self):
        """ cancel timeout to login """
        if self.__terminate_later is not None:
            self.__terminate_later.cancel()
        self.__terminate_later = None

    def __login_timeout(self):
        """ set timeout to login correctly"""
        self.__terminate_later = reactor.callLater(10, self.__terminate)

    def send_message(self, message):
        self.sendLine(message.encode())

    def connectionMade(self):
        self._peer = self.transport.getPeer()
        print(f"Connencted from {self._peer.host}:{self._peer.port}")
        # adding client to server list
        self.factory.clients.append(self)
        # start timer for success login
        self.__login_timeout()
        self.send_message("Привет!")

    def connectionLost(self, reason=connectionDone):
        print(f"Disconnected from {self._peer.host}:{self._peer.port}  Reason: {connectionDone.getErrorMessage()}")
        self.factory.clients.remove(self)
        self.__cancel_login_timeout()

    def lineReceived(self, line):
        content = line.decode('utf-8', 'ignore')
        content = make_printable(content)
        print(strftime(f"[%H:%M:%S] Message from '{self.login}' [{self._peer.host}:{self._peer.port}]:{content}",
                       gmtime()))
        if self.login is not None:
            if len(content) > 0:
                # команды для закрытия соединения
                if content.startswith("/quit"):
                    self.send_message("Пока!")
                    self.__terminate()
                    return

                content = strftime(f"[%H:%M:%S] {self.login}: {content}", gmtime())
                self.factory.history_message(content)
                for user in self.factory.clients:
                    if user is not self:
                        user.message(content.encode())
        else:
            res = re.match(
                r'.*?login:\s*([a-zабвгдеёжзийклмнопрстуфхцчшщъыьэюяАБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ_0-9?!@#$%^&*.\-+ ]{3,16})\s*$',
                content, re.I)

            if bool(res):
                login = res[1].strip()
                if len(login) < 3:
                    self.__terminate(f"Логин короткий! Используйте более 3 символов.")
                    return

                for user in self.factory.clients:
                    if user.login == login:
                        self.__terminate(f"Логин {login} занят, попробуйте другой")
                        return

                self.__cancel_login_timeout()
                self.login = login
                self.send_message(f"Добро пожаловать, {self.login}!")
                self.factory.send_history(self)
            else:
                self.send_message(
                    "Укажите логин не менее 3-х и не более 16-ти печатных символов в формате: login:{name}")


class Server(ServerFactory):
    protocol = ServerProtocol
    clients: list
    history: list

    def startFactory(self):
        self.clients = []
        self.history = []
        print("Сервер запущен, ждём подключений...")

    def stopFactory(self):
        print("Сервер остановлен!")

    def history_message(self, message):
        if len(self.history) >= 10:
            del self.history[0]
        self.history.append(message)

    def send_history(self, client):
        for s in self.history:
            client.send_message(s)


reactor.listenTCP(1234, Server())
reactor.run()

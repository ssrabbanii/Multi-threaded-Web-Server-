from socket import socket, AF_INET, SOCK_STREAM
from threading import Thread, Lock
from os.path import getmtime, getsize
from datetime import datetime
from os import utime

lock = Lock()

def logRequest(headers, requestType, filename, response):

	# add time
	content = datetime.now().strftime('[%x %X] ')

	# add requestType
	content += requestType + '\t'

	# add IP
	for i in headers:
		if 'host' in i.lower():
			content += i.split(': ')[1].replace('\r', '') + '\t'

	# add file name
	content += filename + '\t'

	# add response type
	content += response.split(b' ')[1].decode()

	# add newline
	content += '\n'

	# append to file
	f = open('log.txt', mode='a')
	f.write(content)
	f.close()

def getResponseHeaders(file, size=-1, lastMod = ''):
	timeFormat = '%a, %d %b %Y %X GMT'

	# add date header
	timestamp = datetime.now().timestamp()
	date = datetime.utcfromtimestamp(timestamp).strftime(timeFormat);
	headers = 'Date: {}\n'.format(date).encode()

	# add Last-Modified header
	timestamp = getmtime(file)
	lastModified = datetime.utcfromtimestamp(timestamp).strftime(timeFormat);	
	headers += 'Last-Modified: {}\n'.format(lastModified).encode()

	# add Content-Length header
	size = getsize(file) if size == -1 else size
	headers += 'Content-Length: {}\n'.format(size).encode()

	# add a blank line to signal end of headers
	headers += b'\n'

	# check if Last-Modified header of request matches
	is304 = True if lastMod == lastModified else False
	
	return headers, is304

def get404Header(filename):
	header = 'HTTP/1.1 404 Not Found\n\nFile {} Not Found'.format(filename)
	return header.encode()

def handle_request(request):

	res200 = 'HTTP/1.1 200 OK\n'.encode()
	res400 = 'HTTP/1.1 400 Bad Request\n\nRequest Not Supported'.encode()


	# Parse HTTP headers
	headers = request.split('\n')
	fields = headers[0].split()
	request_type = fields[0]
	filename = fields[1][1:].split('?')[0]

	# default response
	response = res400
	keepAlive = False

	# self explanatory
	if filename == '':
		filename = 'index.html'

	# set keepAlive variable according to connection header
	for i in headers:
		if 'connection' in i.lower():
			value = i.split(': ')[1].split('\r')[0]
			if value.lower() == 'keep-alive':
				keepAlive = True

	# used POST request to modify file.txt from client-side
	if request_type == 'POST' and filename == 'file.txt':
		
		content = 'file.txt Last-Modified Updated!'.encode()
		
		now = datetime.now().timestamp()
		utime(filename, (now, now))

		resHeaders, is304 = getResponseHeaders(filename, len(content))

		response = res200 + resHeaders
		response += content
		
	# process GET & HEAD requests
	if request_type == 'GET' or request_type == 'HEAD':

		try:
			content = b''
			fin = open(filename, mode='rb')

			if request_type == 'GET':
				content = fin.read()

			fin.close()

			# variable to save header if-modified-since from request
			lastMod = ''
			
			for i in headers:
				if 'if-modified-since' in i.lower():
					lastMod = i.split(': ')[1].split('\r')[0]

			# generate response headers accordingly, -1 here so content-length will be calculated
			resHeaders, is304 = getResponseHeaders(filename, -1, lastMod)

			# is304 is true when last-modified & if-modified-since are same
			if is304:
				response = 'HTTP/1.1 304 Not Modified\n'.encode() + resHeaders
				logRequest(headers, request_type, filename, response)
				return response, keepAlive
				
			response = res200 + resHeaders
			response += content

		# if file doesn't exist send 404
		# and close connection (request's status keeps saying 'pending'
		# and javascript doesn't receive 404 when I don't
		# close connection, I guess it starts waiting for timeout)
		except FileNotFoundError:
			response = get404Header(filename)
			keepAlive = False

	# log the request & response
	logRequest(headers, request_type, filename, response)

	if response == res400:
		return response, False

	return response, keepAlive

# thread function
def threaded(connection):
	while True:
		request = connection.recv(1024)

		# break on empty request
		if not request:
			break;

		# get & send response from handle_request
		response, keepAlive = handle_request(request.decode())
		connection.sendall(response)

		# close connection and break loop when keepAlive is False
		if keepAlive == False:
			connection.close()
			break

	# lock.release()

def Main():
	port = 12000
	server = socket(AF_INET, SOCK_STREAM)
	server.bind(('127.0.0.1', port))
	server.listen(1)

	print("server listening on port | {}\n".format(port));

	# wait for connection
	# create new thread for each connection
	while True:

		connection, addr = server.accept()

		# lock.acquire()

		print('\nConnected to | {}:{}'.format(addr[0], addr[1]))

		t = Thread(target=threaded, args=(connection,))
		t.start()

	server.close()

Main();

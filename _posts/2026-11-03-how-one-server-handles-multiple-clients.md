---
layout: post
title: "From Blocking Sockets to Event Loops"
date: 2026-11-03
categories: [Systems]
description: "A question-led explanation of how a server moves from blocking reads to an event loop, and how real servers use workers."
toc:
  - title: "Why does one idle client stop this server?"
    url: "#why-does-one-idle-client-stop-this-server"
    children:
      - title: "What happens when a client connects?"
        url: "#what-happens-when-a-client-connects"
      - title: "Where does the server get stuck?"
        url: "#where-does-the-server-get-stuck"
      - title: "Can the OS accept data while the application is stuck?"
        url: "#can-the-os-accept-data-while-the-application-is-stuck"
  - title: "How does an event loop avoid waiting on one socket?"
    url: "#how-does-an-event-loop-avoid-waiting-on-one-socket"
    children:
      - title: "What does socket readiness mean?"
        url: "#what-does-socket-readiness-mean"
      - title: "How does Linux report ready sockets?"
        url: "#how-does-linux-report-ready-sockets"
      - title: "Why combine readiness with non-blocking sockets?"
        url: "#why-combine-readiness-with-non-blocking-sockets"
      - title: "What happens when many sockets are ready?"
        url: "#what-happens-when-many-sockets-are-ready"
      - title: "Can we put these pieces together in Python?"
        url: "#can-we-put-these-pieces-together-in-python"
  - title: "How is this used by real servers?"
    url: "#how-is-this-used-by-real-servers"
    children:
      - title: "What happens to an HTTP request?"
        url: "#what-happens-to-an-http-request"
      - title: "Why might the application server use threads?"
        url: "#why-might-the-application-server-use-threads"
      - title: "What if the event loop has CPU work to do?"
        url: "#what-if-the-event-loop-has-cpu-work-to-do"
      - title: "How do servers use more than one CPU core?"
        url: "#how-do-servers-use-more-than-one-cpu-core"
---

A server can have hundreds or thousands of clients connected to it. But consider a much smaller situation: one client connects and then sends nothing. Can that one idle client stop the server from serving everyone else?

To understand why this happens, let's follow a connection from the moment the server accepts it. Then we'll change just one thing: instead of reading from a particular client and waiting, we'll ask the operating system which sockets are ready.

## Why does one idle client stop this server? {#why-does-one-idle-client-stop-this-server}

### What happens when a client connects? {#what-happens-when-a-client-connects}

Imagine a TCP server listening on port \`65432\`, and two clients, A and B.

The server creates a listening socket, binds it to the address and port, and calls \`listen()\`. The socket is now waiting for incoming TCP connections.

When client A connects, the TCP handshake is handled by the operating system. Once the connection is established and ready for the application to accept, it is made available through the listening socket's pending connection queue.

The server application obtains that connection by calling:

~~~python
client_socket, address = server_socket.accept()
~~~

The returned \`client_socket\` is a new socket for communicating with client A. The original \`server_socket\` remains the listening socket; it is used to accept other connections.

That distinction matters: one listening socket can produce many connected client sockets. The server needs to keep track of those client sockets separately.

### Where does the server get stuck? {#where-does-the-server-get-stuck}

Consider this simplified server:

~~~python
while True:
    client, address = server.accept()

    data = client.recv(1024)  # Wait for data from this client.
    print(data)

    client.close()
~~~

Now follow what happens:

1. Client A connects. \`accept()\` returns A's connected socket.
2. The server calls \`A.recv(1024)\`.
3. A has not sent anything, so \`recv()\` waits.
4. Client B connects. The server does not call \`accept()\` again because it is still inside A's \`recv()\`.
5. Even if B sends data, this application does not get around to accepting B.

The important point is not that the server has only one socket. It is that the only thread running this code is blocked inside a read from A.

### Can the OS accept data while the application is stuck? {#can-the-os-accept-data-while-the-application-is-stuck}

Yes. The operating system and the server application are doing different parts of the work.

When B connects, the operating system can complete the TCP handshake and place the connection in the listening socket's pending queue. When data arrives for an established connection, the OS handles the network traffic and places received bytes in that connection's receive buffer.

But the application can only call \`recv()\` on B after it has accepted B and obtained B's connected socket. Our code is still waiting inside A's \`recv()\`.

So there are two separate facts:

- The operating system can make progress receiving network traffic for multiple connections.
- Our application is not making progress on B because its thread is blocked reading A.

We need a way to wait for activity across A, B, and the listening socket, rather than entering a blocking read on one client at a time.

## How does an event loop avoid waiting on one socket? {#how-does-an-event-loop-avoid-waiting-on-one-socket}

### What does socket readiness mean? {#what-does-socket-readiness-mean}

Instead of immediately calling \`recv()\` on A, imagine asking the OS:

**Among these sockets, which ones can I read from without waiting?**

The OS can report that a socket is *ready* for a particular operation.

For a TCP server, the useful cases are:

- The listening socket is readable when a connection is waiting to be accepted. We can call \`accept()\`.
- A connected socket is readable when received bytes are available. It is also reported readable when the peer has closed its sending side, so we can discover the disconnect.
- A connected socket is writable when the OS can accept some outgoing bytes without the write having to wait.

This is called **I/O readiness**. It reports whether an operation can make progress now; it does not mean the application has received a complete request.

For example, a client might send an HTTP request in several TCP segments. A readable notification may mean that only the first part has arrived. TCP gives the application a stream of bytes, not one complete message per read. The application must keep the partial data and work out when the request is complete.

### How does Linux report ready sockets? {#how-does-linux-report-ready-sockets}

On Linux, a process refers to an open socket using a **file descriptor**, usually a small integer such as \`4\` or \`7\`. When Python calls \`recv()\`, it ultimately asks the OS to read from the socket represented by that descriptor.

Linux provides **epoll** to monitor many file descriptors for readiness. It has three operations that are useful to understand:

1. \`epoll_create1()\` creates an epoll instance. Think of it as the OS object that holds the set of descriptors we want to monitor.
2. \`epoll_ctl()\` adds a descriptor to that set, changes what events we want for it, or removes it.
3. \`epoll_wait()\` waits until monitored descriptors have events to report. It returns the descriptors and the events that are ready.

For our server, we would register the listening socket for read readiness. When a client connects, we accept it and register the new client socket for read readiness too. Later, \`epoll_wait()\` can report either the listening socket or any client socket whose state is ready.

This means the application does not need to call \`recv()\` on every client just to discover that most of them have no data. It waits for the OS to report sockets that are ready.

Linux is not the only system with a readiness mechanism. Other operating systems expose their own interfaces, such as kqueue on BSD-based systems. Python's \`selectors\` module provides a common interface for this kind of I/O multiplexing. On Linux, \`selectors.DefaultSelector()\` normally uses epoll underneath.

We'll use \`selectors\` in Python. The OS still performs the readiness monitoring; Python gives us a convenient way to register sockets and receive the results.

### Why combine readiness with non-blocking sockets? {#why-combine-readiness-with-non-blocking-sockets}

Suppose the OS reports that client B is readable. Our event loop then calls \`B.recv(1024)\`.

Why should B be non-blocking if the OS has already told us it is ready?

Because readiness is a report about the socket's state when the OS checked it. It is not a reservation of the available bytes for our next read. The state can change before our code performs the operation. For example, another thread could read the available bytes first.

With a blocking socket, our event-loop thread could then wait inside \`recv()\`. While it waits, it cannot return to the loop to handle other ready sockets.

A non-blocking socket behaves differently. If the read cannot make progress immediately, it returns control instead of waiting. In Python, the operation raises \`BlockingIOError\`. The event loop catches that condition and moves on.

Readiness and non-blocking mode solve different parts of the problem:

- Readiness tells the application which socket is worth trying.
- Non-blocking mode prevents an individual read or write from holding up the event-loop thread if the socket is no longer ready.

That is why we set connected sockets to non-blocking mode before using them in the event loop.

### What happens when many sockets are ready? {#what-happens-when-many-sockets-are-ready}

Suppose 50 client sockets become readable. The OS reports ready events to the event loop, and the loop handles the events it receives.

While it is handling those events, another 60 clients might become readable. The loop does not need to interrupt the current callback. It finishes the work it has chosen to do, then waits for events again. The OS can report sockets that are still ready, including sockets that were not returned in the earlier batch.

There are two Linux details behind this behaviour.

**First, one epoll wait does not have to return every ready descriptor.** \`epoll_wait()\` takes a maximum number of events to return in that call. If more descriptors are ready, the remaining ready descriptors can be returned by later calls. Python's \`selectors\` interface hides this low-level argument from our example.

**Second, Linux epoll uses level-triggered mode by default.** If a socket still has unread bytes, it remains readable. If the event loop reads only part of those bytes, the socket can be reported as ready again on a later wait. This is useful because the application does not have to drain every byte in one callback.

There is also an edge-triggered mode. With edge-triggered notification, the application generally needs to keep reading until the operation reports that it would block—\`EAGAIN\` at the OS level, exposed as \`BlockingIOError\` in Python. Otherwise, it may leave data unread and not receive another notification just because that data is still there.

Now consider a different problem: one client is continuously sending data. If the event loop reads from that client forever before handling another socket, other clients can be delayed. The readiness API does not decide how much application work to do for each client. The server must make that decision.

A common approach is to limit the work done for one connection in a single turn—for example, read at most a fixed number of bytes, process a bounded number of messages, then return to the event loop. Our example below reads at most 1024 bytes each time it handles a client socket.

### Can we put these pieces together in Python? {#can-we-put-these-pieces-together-in-python}

Python's \`selectors\` module lets us build the loop without calling epoll directly. We'll build the server in small pieces.

#### 1. Which sockets should the selector watch?

Create the selector and the listening socket. The listening socket must be non-blocking because it will be handled by the same event loop as the clients.

~~~python
import selectors
import socket

selector = selectors.DefaultSelector()

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind(("127.0.0.1", 65432))
server.listen()
server.setblocking(False)

selector.register(server, selectors.EVENT_READ, data="server")
~~~

The last line registers the listening socket for read readiness. For this socket, a read event means a connection is waiting to be accepted.

The \`data\` argument lets us attach information to a registration. We'll use it to distinguish the listening socket from client sockets when events come back.

#### 2. What do we do when the listening socket is ready?

A read event on the listening socket means we can try \`accept()\`. The returned socket is for the new client; it is not the listening socket.

~~~python
def accept_client(server_socket):
    client, address = server_socket.accept()
    print(f"Connected: {address}")

    client.setblocking(False)
    selector.register(client, selectors.EVENT_READ, data="client")
~~~

We set the accepted socket to non-blocking mode and register it too. From this point, the selector can report when that client has data to read.

#### 3. What do we do when a client socket is ready?

Try to read the available bytes. Because the socket is non-blocking, the read will not wait if the socket is no longer ready.

~~~python
def read_client(client):
    try:
        data = client.recv(1024)
    except BlockingIOError:
        return

    if data:
        print(f"Received: {data!r}")
    else:
        # recv() returns b"" when the peer has closed its sending side.
        selector.unregister(client)
        client.close()
~~~

There are two possible results to notice:

- If \`data\` contains bytes, we received some of the client's stream. It may be a whole message or only part of one.
- If \`data\` is \`b""\`, the peer has closed its sending side. We remove the socket from the selector and close it.

This handler reads no more than 1024 bytes per event. It does not loop until the client has no more data, so a continuously active client cannot keep this callback running indefinitely.

#### 4. Where does the event loop happen?

We now have one handler for the listening socket and one for client sockets. The loop waits for ready events and chooses the handler using the \`data\` value we registered earlier.

~~~python
try:
    while True:
        events = selector.select()

        for key, mask in events:
            if key.data == "server":
                accept_client(key.fileobj)
            else:
                read_client(key.fileobj)
finally:
    selector.close()
    server.close()
~~~

\`selector.select()\` waits until at least one registered socket is ready, then returns the ready registrations. \`key.fileobj\` is the socket we registered. The loop accepts a new client when the listening socket is ready, or reads from a client when its socket is ready.

Put the setup, the two functions, and this loop in one Python file in that order. Run it, then open two terminals and connect from each:

~~~bash
nc 127.0.0.1 65432
~~~

Type some text in either terminal. The server prints data from whichever client has sent it. If one terminal stays idle, the server can still read from the other.

This is a small demonstration of the mechanism, not a complete server. It has no response-writing path, output buffer, application-protocol parser, or robust handling for every socket error. Those need additional state and write-readiness handling. The point here is narrower: the event loop does not block waiting for data from one particular client.

## How is this used by real servers? {#how-is-this-used-by-real-servers}

We've built a TCP server that watches its client sockets. But when you open a website, the process that accepts your browser connection may not be the process that runs the application's business logic.

Let's follow one request to see where the event loop fits.

### What happens to an HTTP request? {#what-happens-to-an-http-request}

Suppose your browser requests:

~~~http
GET /orders/42 HTTP/1.1
Host: example.com
~~~

A common deployment places a web server such as Nginx in front of an application server such as Tomcat.

Nginx accepts the browser's TCP connection, reads the HTTP request, and decides what to do with it. If the request is for a static file that Nginx is configured to serve, it may return that file itself. If the request needs application logic, Nginx forwards it to the application server.

Tomcat receives that forwarded request on a separate connection. A Java servlet can inspect the path \`/orders/42\`, call application code to fetch order 42, query a database, and construct the HTTP response. Tomcat then sends the response back to Nginx, which sends it to the browser.

The connections are distinct:

~~~text
Browser  -- HTTP connection -->  Nginx
Nginx    -- upstream connection -->  Tomcat
Tomcat   -- database connection -->  Database
~~~

Nginx does not pass the browser's socket to Tomcat. Nginx reads from the browser socket and writes the request to its own upstream connection. Tomcat reads from that other connection.

This distinction helps answer the next question: do Nginx and Tomcat have to use the same concurrency model? No. They are separate programs, managing separate connections, and can make different choices.

### Why might the application server use threads? {#why-might-the-application-server-use-threads}

Nginx commonly uses an event-driven worker model for network connections. Tomcat can instead use a pool of worker threads to process incoming requests.

Imagine two requests arrive at Tomcat:

- Request A needs a database query that takes 200 milliseconds.
- Request B needs a database query that takes 10 milliseconds.

With a worker-thread model, Tomcat can assign A to one thread and B to another. Thread A may block while waiting for the database. During that wait, the operating system can schedule thread B, which can continue processing its request.

This is convenient because application code can be written in a direct, sequential style: call the database, wait for the result, then build the response. The waiting thread is not available to process another request during that time, but other worker threads can do so.

The trade-off is that threads consume memory and need to be scheduled. A server cannot create an unlimited number of worker threads. It uses a bounded pool and must decide what happens when all workers are busy.

An event-loop-based application server makes a different choice. When an asynchronous database operation starts, the handler can suspend instead of blocking the event-loop thread. The loop can then handle another ready connection. When the database operation completes, the runtime makes the suspended work runnable again.

Neither model removes the database's 200-millisecond wait. They differ in what the server's execution thread does during that wait.

### What if the event loop has CPU work to do? {#what-if-the-event-loop-has-cpu-work-to-do}

An event loop is useful when a task spends much of its time waiting for I/O. It does not make CPU work disappear.

Imagine an asynchronous Python request handler that receives a request to resize 500 large images. If it performs all the image processing directly inside the event-loop thread, that thread is busy calculating pixels. It cannot return to the loop to process socket events for other clients until the calculation finishes.

The same problem occurs if an asynchronous handler calls a blocking database library. The function waits for the database without yielding control to the event loop, so the loop is stuck for the duration of that call.

The usual fix depends on the work:

- Use an asynchronous database or network client when the operation is I/O-bound and has an async interface.
- Run blocking I/O calls in a worker thread when an asynchronous equivalent is not available.
- Move CPU-heavy work, such as image processing, to a process pool so it can run outside the event-loop thread.

This is why an event-loop server may still use threads or processes. The event loop manages socket readiness; worker threads or processes handle work that should not block that loop.

### How do servers use more than one CPU core? {#how-do-servers-use-more-than-one-cpu-core}

One event loop usually runs on one thread. That thread can switch between many connections as their I/O becomes ready, but it executes one piece of its code at a time. Having 1,000 sockets registered with the loop does not mean 1,000 pieces of Python code are running in parallel.

To run work on multiple CPU cores, a server can start multiple worker processes. Each process has its own memory space and can run its own event loop.

Nginx uses a master-and-worker process model. The master process starts and manages worker processes. Each worker handles connections using its own event loop. The operating system schedules runnable workers on available CPU cores; a worker is not automatically tied to one particular core.

A simplified view is:

~~~text
Nginx master process
    |
    +-- Worker process 1 -- Event loop 1
    |
    +-- Worker process 2 -- Event loop 2
    |
    +-- Worker process 3 -- Event loop 3
~~~

The workers can run on different cores at the same time. How incoming connections are shared among workers depends on the server's configuration and the way its listening sockets are set up.

There are therefore two different kinds of concurrency in this design:

- Inside one worker, its event loop takes turns handling I/O for many connections.
- Across worker processes, the operating system can run different workers in parallel on different CPU cores.

Because processes have separate memory spaces, worker 1 cannot directly read a Python object stored in worker 2's memory. If workers need to share application data, they need an explicit mechanism such as shared memory, a database, a cache, or a message broker.

---

We started with one blocking call: \`recv()\`. While it waited for client A, the server's application thread could not accept or read from client B.

An event loop changes where the waiting happens. The application asks the OS to report which sockets are ready, then handles those sockets using non-blocking operations. Real servers use that technique for connection handling, and combine it with threads or worker processes when application work needs a different execution model.

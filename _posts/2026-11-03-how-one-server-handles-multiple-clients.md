---
layout: post
title: "From Blocking Sockets to Event Loops"
date: 2026-11-03
categories: [Systems]
description: "How servers manage many connections, why event loops help, and how worker processes use multiple CPU cores."
toc:
  - title: "How Can One Server Handle Multiple Clients?"
    url: "#how-can-one-server-handle-multiple-clients"
    children:
      - title: "How does data reach the server?"
        url: "#how-does-data-reach-the-server"
      - title: "Why does a blocking server get stuck?"
        url: "#why-does-a-blocking-server-get-stuck"
      - title: "What should the server do instead?"
        url: "#what-should-the-server-do-instead"
      - title: "Which parts belong to the OS and Python?"
        url: "#which-parts-belong-to-the-os-and-python"
  - title: "Understanding the Event Loop"
    url: "#understanding-the-event-loop"
    children:
      - title: "What are we waiting for?"
        url: "#what-are-we-waiting-for"
      - title: "How does the OS watch many sockets?"
        url: "#how-does-the-os-watch-many-sockets"
      - title: "Why must sockets be non-blocking?"
        url: "#why-must-sockets-be-non-blocking"
      - title: "How does the event loop handle clients?"
        url: "#how-does-the-event-loop-handle-clients"
      - title: "Can we build this in Python?"
        url: "#can-we-build-this-in-python"
  - title: "How Do Real Servers Use Event Loops?"
    url: "#how-do-real-servers-use-event-loops"
    children:
      - title: "Where does the web server fit?"
        url: "#where-does-the-web-server-fit"
      - title: "What does the application server do?"
        url: "#what-does-the-application-server-do"
      - title: "Do both servers need an event loop?"
        url: "#do-both-servers-need-an-event-loop"
      - title: "Why use an event loop instead of threads?"
        url: "#why-use-an-event-loop-instead-of-threads"
      - title: "Can one event loop use multiple CPU cores?"
        url: "#can-one-event-loop-use-multiple-cpu-cores"
---

A server can have many clients connected at the same time. But how does one server process keep track of them without getting stuck waiting for one client?

Let's start with what happens when a client sends data.

## How Can One Server Handle Multiple Clients? {#how-can-one-server-handle-multiple-clients}

### How does data reach the server? {#how-does-data-reach-the-server}

Suppose Client A sends \`PING\`.

1. The client asks its operating system to send bytes through its socket.
2. The operating system handles the TCP/IP work and sends the data over the network.
3. The server's operating system receives the packets and places the data in the socket's receive buffer.
4. The server application reads those bytes through the socket API. In Python, it might call \`recv()\`.

The application does not read directly from the network interface. The operating system receives the network data; the application accesses it through the socket.

### Why does a blocking server get stuck? {#why-does-a-blocking-server-get-stuck}

Imagine a simple server that handles one client from beginning to end:

1. Accept a connection.
2. Read from that client.
3. Process the request and respond.
4. Wait for that client to disconnect.
5. Accept the next connection.

Now Client A connects but sends nothing. The server calls \`recv()\` and waits.

While it waits, Clients B and C connect and send data. Their data can reach the operating system and sit in their socket receive buffers. But the application is still blocked reading from A.

**The OS has received data for B and C, but the server application is still waiting for A.**

The problem isn't that the operating system cannot receive multiple connections. It's that our application is waiting on one socket at a time.

### What should the server do instead? {#what-should-the-server-do-instead}

What if the server could ask:

> Which of my sockets can I read from right now?

Then it wouldn't have to call \`recv()\` on A and wait. It could read B if B has data, accept a new connection if one is waiting, and come back to A when A becomes ready.

That's the central idea behind an **event loop**: wait for activity across many sockets, then handle the sockets that are ready.

### Which parts belong to the OS and Python? {#which-parts-belong-to-the-os-and-python}

Creating sockets, accepting connections, sending and receiving bytes, and waiting for I/O readiness all rely on operating-system facilities.

Python gives us convenient interfaces to those facilities through modules such as \`socket\` and \`selectors\`. Other languages expose the same underlying capabilities through different APIs.

We'll use Python for the examples because the code is easy to follow. The event-loop model itself is not specific to Python.

---

## Understanding the Event Loop {#understanding-the-event-loop}

We now have a better question: **how can the server wait for activity on many sockets without checking each one in turn?**

To answer that, we need to understand what the operating system can tell us.

### What are we waiting for? {#what-are-we-waiting-for}

We're waiting for a socket to become **ready** for an operation.

For example:

- A listening socket becomes readable when a new connection is waiting to be accepted.
- A client socket becomes readable when data is available to read, or when the peer has disconnected.
- A socket becomes writable when it can accept some more outgoing data without the write operation having to wait.

This is called **I/O readiness**.

One important detail: readable does not mean a complete request has arrived. TCP is a byte stream. A request may arrive in pieces, so the application still needs to assemble and interpret those bytes.

### How does the OS watch many sockets? {#how-does-the-os-watch-many-sockets}

On Unix-like systems, an open socket is represented to a process by a **file descriptor**—a small integer handle the process uses when asking the OS to perform operations on that socket.

So how can we watch many descriptors?

Linux provides an interface called **epoll**. Its job can be understood in three operations:

- \`epoll_create1()\` creates an epoll instance: a place where the OS can track the descriptors we're interested in.
- \`epoll_ctl()\` adds, modifies, or removes a descriptor and the events we want to watch.
- \`epoll_wait()\` waits until one or more watched descriptors are ready, then returns the ready events.

The key benefit is that our application waits for readiness across the registered descriptors instead of repeatedly trying to read from every client.

Other operating systems provide similar mechanisms, such as kqueue. Python's \`selectors\` module gives us a common interface across platforms. On Linux, \`selectors.DefaultSelector()\` normally uses epoll underneath.

We can use that interface to learn the event loop without writing Linux-specific code.

### Why must sockets be non-blocking? {#why-must-sockets-be-non-blocking}

Suppose the OS reports that Client B is ready to read. Before our program calls \`recv()\`, the available data might be consumed or the socket's state might change.

Readiness is a snapshot, not a promise. The socket's state can change before the read happens—for example, another thread may consume the available data. If the socket is blocking, our event-loop thread could then wait on B, bringing back the very problem we're trying to avoid.

A non-blocking socket behaves differently: if an operation cannot proceed immediately, it returns instead of waiting. In Python, that situation is reported as \`BlockingIOError\`.

So the two pieces work together:

- **Readiness notification** tells us which socket is worth trying.
- **Non-blocking I/O** ensures the attempt won't hold up the event loop if the socket isn't ready anymore.

### How does the event loop handle clients? {#how-does-the-event-loop-handle-clients}

Let's follow one pass through the loop.

1. Register the listening socket so we're notified when a connection is waiting.
2. When a client connects, accept it and register its socket too.
3. Wait for the OS to report ready sockets.
4. If the listening socket is ready, accept a client. If a client socket is ready, read from it.
5. Go back to waiting.

That's the whole pattern: **wait, handle what's ready, repeat**.

Now let's build it. Rather than presenting a large finished program and explaining it afterwards, we'll add each part when the story needs it.

### Can we build this in Python? {#can-we-build-this-in-python}

#### 1. How do we ask Python to watch sockets?

First, create a selector and a non-blocking listening socket. The listening socket is the entry point for new clients.

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

The \`register()\` call tells the selector: "Notify me when this socket is ready for reading." For a listening socket, that means a connection is waiting.

#### 2. What should happen when a client connects?

When the listening socket becomes readable, we accept the connection. The new client socket must also be non-blocking, and we register it to watch for incoming data.

Add this function:

~~~python
def accept_client(server_socket):
    client, address = server_socket.accept()
    print(f"Connected: {address}")

    client.setblocking(False)
    selector.register(client, selectors.EVENT_READ, data="client")
~~~

We use the selector's \`data\` field to distinguish the listening socket from connected client sockets.

#### 3. What should happen when a client sends data?

When a client socket becomes readable, we try to receive the available bytes.

~~~python
def read_client(client):
    try:
        data = client.recv(1024)
    except BlockingIOError:
        # It was no longer ready when we tried to read.
        return

    if data:
        print(f"Received: {data!r}")
    else:
        # An empty result means the peer disconnected.
        selector.unregister(client)
        client.close()
~~~

Why check for an empty result? Because \`recv()\` returning \`b""\` on a TCP socket means the peer has closed its sending side. We should stop monitoring that socket and close it.

Also notice that \`recv(1024)\` reads *up to* 1024 bytes. It doesn't promise to return one complete application request.

#### 4. How do we bring the pieces together?

We now have handlers for both kinds of sockets. The loop asks the selector for ready sockets and dispatches each one to the appropriate handler.

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

Put the three snippets together in the order shown: setup first, then the two handler functions, then the loop. You now have a small multi-client TCP server.

Run it, then connect from two separate terminals:

~~~bash
nc 127.0.0.1 65432
~~~

Send text from either terminal. The server handles whichever socket is ready; it doesn't sit inside a read waiting for one particular client.

This is deliberately a small example. It focuses on the event loop, not on building a complete network server. A production server also needs output buffering, write readiness, protocol framing, error handling, and graceful shutdown.

### So, what changed?

Our first server waited for a particular client and couldn't make progress while that client was idle.

The event-loop version asks the operating system which sockets are ready, then performs non-blocking operations on those sockets.

**Instead of waiting for one client, we wait for whichever client is ready.**

That's the foundation of the event-loop model.

---

## How Do Real Servers Use Event Loops? {#how-do-real-servers-use-event-loops}

So far, we've looked at one server accepting connections directly from clients. Real applications often have more than one server component between the client and the code that performs the actual work.

Let's look at that setup and see where event loops fit.

### Where does the web server fit? {#where-does-the-web-server-fit}

Imagine you open a website. Your browser sends an HTTP request. That request often reaches a **web server** such as Nginx first.

A web server commonly handles work at the HTTP and connection layer:

- Accepting connections from clients.
- Reading and parsing incoming HTTP requests.
- Managing connection details and timeouts.
- Serving static files, when configured to do so.
- Forwarding requests to an application server when application logic is needed.

A request does not necessarily arrive in one neat piece. The HTTP headers or body may be delivered across multiple TCP reads. The web server must keep track of the bytes it has received and determine when it has enough information to process or forward the request.

For example, Nginx can buffer a request before forwarding it, or stream parts of the request upstream, depending on its configuration. Either way, it must manage the incoming connection while data is arriving.

This is one reason event-driven I/O is useful at the web-server layer: many clients may be connected, but only some of them have data to read or work to do at any particular moment.

### What does the application server do? {#what-does-the-application-server-do}

The web server usually doesn't contain all the business logic of an application. It forwards the request to an **application server**, such as a Java application running on Tomcat or a Python application served by Gunicorn.

The application server is responsible for running the application:

- Calling application code.
- Reading or updating data.
- Applying business rules.
- Communicating with databases or other services.
- Producing the response that will be sent back to the client.

The web server and application server communicate over another network connection. They might run on the same machine using different ports, or on separate machines.

For example:

~~~text
Browser
   |
   | HTTP request
   v
Nginx (web server)
   |
   | upstream connection
   v
Tomcat (application server)
   |
   | database query
   v
Database
~~~

The connection from the browser to Nginx and the connection from Nginx to Tomcat are separate connections. Each side manages its own sockets. Nginx does not hand its client socket or event loop to Tomcat; it sends the request over the upstream connection.

### Do both servers need an event loop? {#do-both-servers-need-an-event-loop}

No. The web server and application server make their own concurrency choices.

Nginx commonly uses an event-driven worker model to manage many client and upstream connections. But the application server behind it might use a thread-per-request or thread-pool model.

For example:

- **Event-driven web server + threaded application server:** Nginx manages network connections with an event loop, then Tomcat handles application requests using worker threads.
- **Event-driven web server + asynchronous application server:** Nginx uses its event-driven model, and an async Python application server uses an event loop to manage its own connections and asynchronous work.
- **Threaded web server + threaded application server:** both layers can use threads.
- **Event-driven application server without a separate web-server layer:** an application server can also accept client connections directly.

These are independent architectural decisions. Having an event loop in one layer does not require every other layer to use one.

### Why use an event loop instead of threads? {#why-use-an-event-loop-instead-of-threads}

Let's return to the original problem: many clients connect, and most of the time they are waiting for something—more network data, a database response, or another service.

One approach is to assign a thread to each client. When that client waits for I/O, its thread blocks, and the operating system can schedule another thread.

That model is straightforward, especially when the code is written in a blocking style. But a large number of mostly idle connections can mean a large number of threads. Threads need stack memory, scheduling, and coordination. Context switching between many threads also has a cost.

An event loop takes a different approach:

1. Keep track of many sockets.
2. Ask the operating system which ones are ready.
3. Run the handler for a ready socket.
4. If more I/O is needed, don't block the event-loop thread waiting for it. Return to the loop so it can handle other ready sockets.
5. When the OS reports that more data is ready, continue that connection's work. Async runtimes can suspend and resume coroutines; callback-based loops keep the connection's state separately.

This can support many concurrent I/O connections with far fewer threads.

But an event loop is not automatically better in every situation:

- **Event loops** are effective when work involves lots of concurrent I/O and handlers spend much of their time waiting.
- **Threads** can make blocking code easier to write and can be a good fit when the workload and connection count are manageable.
- **CPU-heavy work** is different. If an event-loop handler spends a long time calculating, it prevents that loop from handling other events until it finishes.

So the choice is not simply "event loops are faster than threads." It depends on the workload, the runtime, and how the application is structured. Many real systems combine both: an event loop for network I/O and a thread or process pool for work that should not run on the event-loop thread. The same rule applies to database calls: if an application uses a blocking database client directly on the event-loop thread, that call can stall the loop too. It needs an asynchronous client or to run outside the loop.

### Can one event loop use multiple CPU cores? {#can-one-event-loop-use-multiple-cpu-cores}

There is one more question. If an event loop handles many clients, does that mean it can use all the CPU cores in the machine?

Not by itself.

A single event loop usually runs on one thread. At any given moment, that thread executes its event-handling code on one CPU core. It can keep many I/O operations in progress, but it does not execute multiple pieces of Python code in parallel just because many clients are connected.

To use multiple cores, servers commonly run **multiple worker processes**. Each process has its own memory space and can run its own event loop.

For example, on a machine with four available CPU cores, a server might start several worker processes:

~~~text
                 Incoming connections
                         |
              Operating system distributes
                  connections to workers
                  /      |      |      \
                 v       v      v       v
              Worker  Worker Worker  Worker
                1       2      3       4
                |       |      |       |
              Loop 1  Loop 2 Loop 3  Loop 4
                |       |      |       |
              Core 1  Core 2 Core 3  Core 4
~~~

This is broadly how Nginx is structured: a master process starts and manages worker processes, and each worker handles connections using an event-driven loop. Each worker runs its own event loop and manages the connections assigned to it. The operating system schedules those processes across the available CPU cores; workers are not necessarily pinned to one particular core.

The exact way connections reach workers depends on the server. A parent process might accept connections and pass them to workers, or workers might share a listening socket and let the operating system distribute incoming connections.

This gives us two levels of concurrency:

- **Within one worker:** its event loop interleaves work across many connections without needing one thread per connection.
- **Across workers:** multiple processes can run in parallel on different CPU cores.

The same idea applies to application servers, although their worker models differ. Some use multiple processes, some use thread pools, and some combine processes with asynchronous event loops.

One final distinction matters: multiple event loops do not automatically share application state. Separate processes have separate memory spaces, so they need an explicit way to share data when required—for example, through a database, cache, or message broker.

---

An event loop solves the problem of waiting efficiently for many I/O operations. Multiple worker processes take that model across CPU cores. And in a real application, the web server and application server can each choose the concurrency model that fits their own responsibilities.

The important idea is not that every server must use an event loop. It's understanding **what is waiting, who is waiting for it, and how the system keeps making progress while it waits.**

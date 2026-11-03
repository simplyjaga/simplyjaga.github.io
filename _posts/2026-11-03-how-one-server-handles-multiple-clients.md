---
layout: post
title: "How Can One Server Handle Multiple Clients?"
date: 2026-11-03
categories: [Systems]
description: "Follow a client request through the operating system and understand why a blocking server gets stuck on one client."
toc:
  - title: "How Can One Server Handle Multiple Clients?"
    url: "#article-start"
    children:
      - title: "What happens when a client sends data?"
        url: "#what-happens-when-a-client-sends-data"
      - title: "Why does a blocking server get stuck?"
        url: "#why-does-a-blocking-server-get-stuck"
      - title: "What do we need instead?"
        url: "#what-do-we-need-instead"
      - title: "The system calls and the programming language"
        url: "#the-system-calls-and-the-programming-language"
  - title: "Understanding the Event Loop"
    url: "#understanding-the-event-loop"
    children:
      - title: "What is an event loop?"
        url: "#what-is-an-event-loop"
      - title: "What is an event?"
        url: "#what-is-an-event"
      - title: "File descriptors and I/O readiness"
        url: "#file-descriptors-and-io-readiness"
      - title: "The event loop lifecycle"
        url: "#the-event-loop-lifecycle"
      - title: "A basic event loop in Python"
        url: "#a-basic-event-loop-in-python"
---

An event loop allows a server to handle many client connections without waiting for each client one at a time. To understand how it works, we first need to see what happens when data travels from a client to a server.

This post explores that flow and then builds towards the event-loop model.

## What happens when a client sends data? {#what-happens-when-a-client-sends-data}

Suppose Client A sends the bytes `PING` to a server.

The data travels through several steps:

1. The client program asks the operating system to send data through its socket. In Python, this is done using methods such as `send()` or `sendall()`.
2. The client's operating system handles the TCP/IP networking work and sends packets through the machine's network interface.
3. The packets travel across the network to the server machine.
4. The server's network interface receives the packets. The server operating system processes them and places the received data in the socket's receive buffer.
5. The server program asks the operating system to read from that socket. In Python, it can call `recv()`. If the socket is blocking and no data is available, the call waits. When data arrives, the operating system makes the waiting operation ready to continue, and `recv()` returns the available bytes.

The application does not read directly from the network interface. The operating system receives the network data and makes it available through the socket. The application accesses it through the socket API.

## Why does a blocking server get stuck? {#why-does-a-blocking-server-get-stuck}

Consider a simple server that handles one client at a time:

1. Call `accept()` and wait for a client connection.
2. Call `recv()` to read data from that client.
3. Process the data and send a response.
4. Continue handling that client until it disconnects.
5. Return to `accept()` to take another client.

Now imagine Client A connects but does not send any data yet.

The server calls `recv()` for Client A. Because the socket is blocking and no data has arrived, the server waits there.

Meanwhile, Client B and Client C connect and send data. The server operating system receives their packets and places the data in their respective socket receive buffers.

But the server program is still waiting inside the `recv()` call for Client A. It has not returned to `accept()` to accept the other connections, so it cannot read their data yet.

**The operating system has received data for B and C, but the application is still waiting for A.**

That's the limitation of this design: waiting for one client's data prevents the server from handling other clients.

## What do we need instead? {#what-do-we-need-instead}

We want the server to find out which client sockets are ready for I/O, rather than block while waiting for one particular client.

For example:

- Client A has no data yet, so the server should not wait on A.
- Client B has sent data, so the server reads and handles B's request.
- Client C has also sent data, so the server handles C.
- When A's data arrives, the server can handle A too.

An **event loop** provides a way to organise this. It waits for activity on multiple sockets and handles the sockets that are ready. Non-blocking I/O is an important part of this approach.

## The system calls and the programming language {#the-system-calls-and-the-programming-language}

The operating system provides interfaces for operations such as creating sockets, accepting connections, sending and receiving data, and waiting for socket events.

Different operating systems expose these capabilities through different system calls and APIs. Programming languages provide their own interfaces around them. For example, Python's `socket` module gives us methods such as `socket()`, `accept()`, `send()`, and `recv()`; these let us work with sockets without writing the low-level operating-system interface ourselves.

For the examples in this post, we'll use **Python** because its code is straightforward to read. The concepts we discuss—sockets, blocking and non-blocking I/O, readiness notifications, and event loops—are operating-system concepts, not features unique to Python. The same ideas can be explored in other languages using their respective APIs.

We'll build the explanation from the data flow and socket operations, then look at how the operating system can notify a server about sockets that are ready and how the event loop uses that information.


---

# Understanding the Event Loop {#understanding-the-event-loop}

In the previous section, we saw the problem with a blocking server: one slow client can keep the server waiting while other clients are ready to be handled.

The key question is: **How can a server wait for activity from many sockets without waiting on each socket individually?**

The operating system provides I/O readiness mechanisms for this. An event loop uses one of these mechanisms to wait for activity across a collection of file descriptors, then handles the ones that are ready.

Let's build that idea one piece at a time.

## What is an event loop? {#what-is-an-event-loop}

An event loop is a repeated cycle:

1. **Wait** for one or more registered resources to become ready.
2. **Collect** the resources for which an event has occurred.
3. **Handle** each ready resource.
4. **Repeat** the cycle.

For a network server, the resources are usually sockets. A socket might become ready because a new client connection is waiting to be accepted, or because an existing client has sent data.

Notice what the server is waiting for. It is not waiting for Client A to send data specifically. It is asking the operating system to tell it when *any registered socket* is ready for an operation.

That distinction is what lets one thread make progress on many connections.

An event loop is not itself a thread, nor is it a special operating-system process. It is a programming pattern: a loop that waits for readiness notifications and dispatches work. It can run on a single thread.

## What is an event? {#what-is-an-event}

An event is a notification that something has happened, or that an operation on a resource can make progress.

For socket programming, two common readiness events are:

- **Read readiness:** reading from the socket should not block. There may be bytes available to read, or the peer may have closed its connection.
- **Write readiness:** writing to the socket should not block at that moment because the socket has room in its send buffer.

Readiness does not mean that an entire request has arrived, or that an entire response can be written in one operation. It only tells us that the corresponding I/O operation can make some progress without waiting.

For example, suppose Client B sends a request in three pieces. The server might receive a read-ready notification after the first piece. It can read the bytes that are currently available, but it must keep track of the request until the remaining pieces arrive.

The event loop handles readiness. The application still has to understand its protocol and decide when it has received a complete message.

## File descriptors and I/O readiness {#file-descriptors-and-io-readiness}

To understand how the operating system watches multiple sockets, we need to understand a file descriptor.

On Unix-like operating systems, a **file descriptor** is a small integer that a process uses as a handle for an open resource. Files, pipes, and sockets can all be represented this way.

For example, when a process creates a socket, the operating system gives it a file descriptor. The process passes that descriptor to operations such as reading, writing, or asking whether the socket is ready.

The descriptor is not the socket data itself. It is a reference the process uses to identify the resource inside the operating system.

### How does the operating system watch many descriptors?

A server could repeatedly ask each socket whether it is ready. But doing that one socket at a time would be inefficient when there are many connections.

Instead, operating systems provide readiness-notification interfaces. On Linux, one such interface is **epoll**:

1. Create an epoll instance.
2. Register the file descriptors you want it to monitor, along with the events you care about (for example, read readiness).
3. Wait for events.
4. The operating system returns the descriptors that are ready.
5. Handle those descriptors and wait again.

The important idea is that the application does not need to continuously call `recv()` on every client socket. It waits for the operating system to report which sockets can make progress.

Different operating systems provide different mechanisms and APIs. Linux provides epoll; BSD-based systems and macOS provide kqueue; and select is another readiness interface. Languages and libraries expose these mechanisms through their own interfaces.

Python's `selectors` module gives us a portable, higher-level interface. `selectors.DefaultSelector()` chooses an appropriate implementation for the platform. On Linux, that will normally use epoll. We can learn the event-loop pattern through this interface without making the whole example depend on Linux-specific calls.

## The event loop lifecycle {#the-event-loop-lifecycle}

Before writing code, let's follow what happens when a server uses an event loop.

**1. Create a listening socket**

The server creates a TCP socket, binds it to an address, and starts listening. This socket is responsible for new incoming connections.

**2. Make the socket non-blocking**

A non-blocking socket does not make the application wait when an operation cannot make progress immediately. Instead, the operation returns with a result indicating that it would block.

For example, if we call `recv()` when no bytes are available, a non-blocking socket raises `BlockingIOError` in Python rather than waiting for data.

We make sockets non-blocking because readiness is a notification that an operation *should* make progress, not a guarantee that it cannot encounter a race or a condition change before we perform the operation. The event loop must never get stuck waiting on one socket.

**3. Register sockets with the selector**

The server registers the listening socket for read events. For a listening socket, read readiness means a connection is waiting to be accepted.

When a client connects, the server accepts it, makes the newly accepted socket non-blocking, and registers that socket for read events too.

**4. Wait for ready sockets**

The event loop calls the selector's `select()` method. The call can wait until at least one registered socket is ready.

This is an important distinction from the blocking `recv()` problem in the previous section: the server is waiting for activity across the registered sockets, not waiting for data from one specific client.

**5. Handle the returned events**

For each ready socket, the server performs the relevant operation:

- If the listening socket is ready, accept a new connection.
- If a client socket is ready, read the available bytes.
- If a client has disconnected, unregister and close its socket.

After handling the events, the loop goes back to waiting.

## A basic event loop in Python {#a-basic-event-loop-in-python}

Python's `selectors` module lets us implement this pattern with a small amount of code.

The example below is a minimal TCP server. It accepts multiple clients and prints data received from each one. It does not implement an application protocol or send responses; its purpose is to make the event loop itself easy to see.

```python
import selectors
import socket

selector = selectors.DefaultSelector()


def accept_connection(server_socket):
    client_socket, address = server_socket.accept()
    print(f"Accepted connection from {address}")

    client_socket.setblocking(False)
    selector.register(client_socket, selectors.EVENT_READ, data="client")


def read_from_client(client_socket):
    try:
        data = client_socket.recv(1024)
    except BlockingIOError:
        # The socket is no longer ready by the time we read it.
        return

    if data:
        print(f"Received from {client_socket.getpeername()}: {data!r}")
        return

    # recv() returning empty bytes means the client disconnected.
    print(f"Client disconnected: {client_socket.getpeername()}")
    selector.unregister(client_socket)
    client_socket.close()


server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server_socket.bind(("127.0.0.1", 65432))
server_socket.listen()
server_socket.setblocking(False)

# None identifies the listening socket in the event loop.
selector.register(server_socket, selectors.EVENT_READ, data=None)

print("Server listening on 127.0.0.1:65432")

try:
    while True:
        # Wait until one or more registered sockets are ready.
        events = selector.select()

        for key, mask in events:
            if key.data is None:
                # A new connection is ready to be accepted.
                accept_connection(key.fileobj)
            else:
                # An existing client has data (or a disconnect) ready.
                read_from_client(key.fileobj)
finally:
    selector.close()
    server_socket.close()
```

Let's connect the code to the lifecycle:

- `DefaultSelector()` creates the selector that manages our registered sockets.
- `setblocking(False)` ensures that accepting or reading does not leave the event loop waiting on one socket.
- `register(..., EVENT_READ)` tells the selector which sockets we want to monitor for read readiness.
- `select()` waits for activity and returns the sockets that are ready.
- `key.fileobj` gives us the socket associated with a returned event. We use `key.data` to distinguish the listening socket from client sockets.
- `recv(1024)` reads the bytes currently available, up to 1024 bytes. It does not promise to return one complete application-level message.
- When `recv()` returns `b""`, the client has closed its sending side, so we unregister and close the socket.

You can run this server and connect to it from multiple terminal windows using a TCP client such as `nc`:

```bash
nc 127.0.0.1 65432
```

Open another terminal and run the same command. Send text from either terminal. The server can receive data from whichever client becomes ready, without being stuck waiting for the other one.

This example deliberately keeps the responsibilities small. A real protocol server would also need to handle partial messages, output buffering, write readiness, errors, timeouts, and orderly shutdown. Those concerns build on the same event-loop foundation.

## Bringing it together

The event loop solves the waiting problem by separating **waiting for I/O readiness** from **performing I/O on a particular socket**.

The operating system monitors registered resources and reports which ones are ready. The event loop processes those notifications, performs non-blocking operations, and then waits again.

The core idea is simple:

**Don't wait for one client. Wait for any client that is ready.**

That is the foundation of an event-driven server. The exact APIs differ across operating systems and programming languages, but the model remains the same.

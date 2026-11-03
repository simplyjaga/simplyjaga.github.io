---
layout: post
title: "How Can One Server Handle Multiple Clients?"
date: 2026-11-03
categories: [Systems]
description: "Why does a blocking server get stuck on one client, and how can an event loop help?"
toc:
  - title: "How Can One Server Handle Multiple Clients?"
    url: "#article-start"
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
---

A server can have many clients connected at the same time. But how does one server process keep track of them without getting stuck waiting for one client?

Let's start with what happens when a client sends data.

## How does data reach the server? {#how-does-data-reach-the-server}

Suppose Client A sends `PING`.

1. The client asks its operating system to send bytes through its socket.
2. The operating system handles the TCP/IP work and sends the data over the network.
3. The server's operating system receives the packets and places the data in the socket's receive buffer.
4. The server application reads those bytes through the socket API. In Python, it might call `recv()`.

The application does not read directly from the network interface. The operating system receives the network data; the application accesses it through the socket.

## Why does a blocking server get stuck? {#why-does-a-blocking-server-get-stuck}

Imagine a simple server that handles one client from beginning to end:

1. Accept a connection.
2. Read from that client.
3. Process the request and respond.
4. Wait for that client to disconnect.
5. Accept the next connection.

Now Client A connects but sends nothing. The server calls `recv()` and waits.

While it waits, Clients B and C connect and send data. Their data can reach the operating system and sit in their socket receive buffers. But the application is still blocked reading from A.

**The OS has received data for B and C, but the server application is still waiting for A.**

The problem isn't that the operating system cannot receive multiple connections. It's that our application is waiting on one socket at a time.

## What should the server do instead? {#what-should-the-server-do-instead}

What if the server could ask:

> Which of my sockets can I read from right now?

Then it wouldn't have to call `recv()` on A and wait. It could read B if B has data, accept a new connection if one is waiting, and come back to A when A becomes ready.

That's the central idea behind an **event loop**: wait for activity across many sockets, then handle the sockets that are ready.

## Which parts belong to the OS and Python? {#which-parts-belong-to-the-os-and-python}

Creating sockets, accepting connections, sending and receiving bytes, and waiting for I/O readiness all rely on operating-system facilities.

Python gives us convenient interfaces to those facilities through modules such as `socket` and `selectors`. Other languages expose the same underlying capabilities through different APIs.

We'll use Python for the examples because the code is easy to follow. The event-loop model itself is not specific to Python.

---

# Understanding the Event Loop {#understanding-the-event-loop}

We now have a better question: **how can the server wait for activity on many sockets without checking each one in turn?**

To answer that, we need to understand what the operating system can tell us.

## What are we waiting for? {#what-are-we-waiting-for}

We're waiting for a socket to become **ready** for an operation.

For example:

- A listening socket becomes readable when a new connection is waiting to be accepted.
- A client socket becomes readable when data is available to read, or when the peer has disconnected.
- A socket becomes writable when it can accept some more outgoing data without the write operation having to wait.

This is called **I/O readiness**.

One important detail: readable does not mean a complete request has arrived. TCP is a byte stream. A request may arrive in pieces, so the application still needs to assemble and interpret those bytes.

## How does the OS watch many sockets? {#how-does-the-os-watch-many-sockets}

On Unix-like systems, an open socket is represented to a process by a **file descriptor**—a small integer handle the process uses when asking the OS to perform operations on that socket.

So how can we watch many descriptors?

Linux provides an interface called **epoll**. Its job can be understood in three operations:

- `epoll_create1()` creates an epoll instance: a place where the OS can track the descriptors we're interested in.
- `epoll_ctl()` adds, modifies, or removes a descriptor and the events we want to watch.
- `epoll_wait()` waits until one or more watched descriptors are ready, then returns the ready events.

The key benefit is that our application waits for readiness across the registered descriptors instead of repeatedly trying to read from every client.

Other operating systems provide similar mechanisms, such as kqueue. Python's `selectors` module gives us a common interface across platforms. On Linux, `selectors.DefaultSelector()` normally uses epoll underneath.

We can use that interface to learn the event loop without writing Linux-specific code.

## Why must sockets be non-blocking? {#why-must-sockets-be-non-blocking}

Suppose the OS reports that Client B is ready to read. Before our program calls `recv()`, the available data might be consumed or the socket's state might change.

If the socket is blocking, a read that can no longer make progress could make our event-loop thread wait on B. That would bring back the very problem we're trying to avoid.

A non-blocking socket behaves differently: if an operation cannot proceed immediately, it returns instead of waiting. In Python, that situation is reported as `BlockingIOError`.

So the two pieces work together:

- **Readiness notification** tells us which socket is worth trying.
- **Non-blocking I/O** ensures the attempt won't hold up the event loop if the socket isn't ready anymore.

## How does the event loop handle clients? {#how-does-the-event-loop-handle-clients}

Let's follow one pass through the loop.

1. Register the listening socket so we're notified when a connection is waiting.
2. When a client connects, accept it and register its socket too.
3. Wait for the OS to report ready sockets.
4. If the listening socket is ready, accept a client. If a client socket is ready, read from it.
5. Go back to waiting.

That's the whole pattern: **wait, handle what's ready, repeat**.

Now let's build it. Rather than presenting a large finished program and explaining it afterwards, we'll add each part when the story needs it.

## Can we build this in Python? {#can-we-build-this-in-python}

### 1. How do we ask Python to watch sockets?

First, create a selector and a non-blocking listening socket. The listening socket is the entry point for new clients.

```python
import selectors
import socket

selector = selectors.DefaultSelector()

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind(("127.0.0.1", 65432))
server.listen()
server.setblocking(False)

selector.register(server, selectors.EVENT_READ, data="server")
```

The `register()` call tells the selector: "Notify me when this socket is ready for reading." For a listening socket, that means a connection is waiting.

### 2. What should happen when a client connects?

When the listening socket becomes readable, we accept the connection. The new client socket must also be non-blocking, and we register it to watch for incoming data.

Add this function:

```python
def accept_client(server_socket):
    client, address = server_socket.accept()
    print(f"Connected: {address}")

    client.setblocking(False)
    selector.register(client, selectors.EVENT_READ, data="client")
```

We use the selector's `data` field to distinguish the listening socket from connected client sockets.

### 3. What should happen when a client sends data?

When a client socket becomes readable, we try to receive the available bytes.

```python
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
```

Why check for an empty result? Because `recv()` returning `b""` on a TCP socket means the peer has closed its connection. We should stop monitoring that socket and close it.

Also notice that `recv(1024)` reads *up to* 1024 bytes. It doesn't promise to return one complete application request.

### 4. How do we bring the pieces together?

We now have handlers for both kinds of sockets. The loop asks the selector for ready sockets and dispatches each one to the appropriate handler.

```python
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
```

Put the three snippets together in the order shown: setup first, then the two handler functions, then the loop. You now have a small multi-client TCP server.

Run it, then connect from two separate terminals:

```bash
nc 127.0.0.1 65432
```

Send text from either terminal. The server handles whichever socket is ready; it doesn't sit inside a read waiting for one particular client.

This is deliberately a small example. It focuses on the event loop, not on building a complete network server. A production server also needs output buffering, write readiness, protocol framing, error handling, and graceful shutdown.

## So, what changed? 

Our first server waited for a particular client and couldn't make progress while that client was idle.

The event-loop version asks the operating system which sockets are ready, then performs non-blocking operations on those sockets.

**Instead of waiting for one client, we wait for whichever client is ready.**

That's the foundation of the event-loop model.

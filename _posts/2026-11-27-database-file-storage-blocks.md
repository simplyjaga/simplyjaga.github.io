---
layout: post
title: "How Does a Database Actually Store Your Rows in Blocks on Disk?"
date: 2026-11-27
categories: [Systems]
description: "Following a 10-row table down to disk to learn how rows become pages, pages become files, and every query ends as a filename, an offset, and a read."
toc:
  - title: "What does the OS actually see?"
    url: "#what-does-the-os-actually-see"
    children:
      - title: "How do rows sit inside a page?"
        url: "#how-do-rows-sit-inside-a-page"
      - title: "What does reading and writing a page look like in code?"
        url: "#what-does-reading-and-writing-a-page-look-like-in-code"
  - title: "What happens as the table grows?"
    url: "#what-happens-as-the-table-grows"
    children:
      - title: "Why does a 10-row table end up in three files?"
        url: "#why-does-a-10-row-table-end-up-in-three-files"
      - title: "How does a page number turn into a file and an offset?"
        url: "#how-does-a-page-number-turn-into-a-file-and-an-offset"
  - title: "Where does an index live?"
    url: "#where-does-an-index-live"
    children:
      - title: "Isn't an index just another table?"
        url: "#isnt-an-index-just-another-table"
      - title: "Why does an index on email look so different from the table?"
        url: "#why-does-an-index-on-email-look-so-different-from-the-table"
      - title: "How does a query find its row?"
        url: "#how-does-a-query-find-its-row"
  - title: "What happens when rows change?"
    url: "#what-happens-when-rows-change"
    children:
      - title: "What do UPDATE and DELETE touch?"
        url: "#what-do-update-and-delete-touch"
      - title: "What happens when an insert lands in the middle?"
        url: "#what-happens-when-an-insert-lands-in-the-middle"
---

Tables look like grids and B+ trees look like nodes with pointers, but
neither exists on disk. What exists is files: plain stretches of bytes.
The clearest way to see how a database turns one into the other is to
build a tiny storage engine ourselves, make the simplest reasonable design
choice at each step, and follow a 10-row table all the way down to
`read` and `write` calls.

## What does the OS actually see? {#what-does-the-os-actually-see}

Files and bytes, nothing more. The OS has no idea what a row, a table, or
an index is. All of that is meaning our engine puts on top of the bytes.

Our first design choice is the unit we read and write: a **page**, a
fixed-size chunk of a file. We never read "a row" from disk; we read the
page that contains it. Pages are numbered from 0, and the page number is
simply how many pages to skip from the start:

```
page 0 → starts at byte 0
page 1 → starts at byte 1 × page_size
page 2 → starts at byte 2 × page_size
```

You'll also hear a page called a **block**. Real engines use pages of
4–16 KB, sized as a multiple of the filesystem's own block size so one
page read lines up cleanly with what the disk reads underneath. To keep
every number countable, our toy engine uses **100-byte pages**, and each
student row takes about 45 bytes, so **a page holds 2 rows**.

### How do rows sit inside a page? {#how-do-rows-sit-inside-a-page}

A page starts with a small header that says how many rows it holds and
the byte where each row begins, and the rows' own data fills the rest of
the page after it. Rows inside a page
are identified by their **position**: the first row is position 0, the
second is position 1.

```
page 4 (100 bytes)
┌──────────────────────────────────────────────────┐
│ header: 2 rows │ pos 0 at byte 10 │ pos 1 at 55  │
│ pos 0:  9 | Kiran | CS | kiran@x.com             │
│ pos 1: 10 | Lata  | ME | lata@x.com              │
└──────────────────────────────────────────────────┘
```

So any row of a table has an address of the form **(page, position)**
within that table. Row 10 above is `(page 4, position 1)` of `students`.
The address only makes sense together with the table: a `courses` table
can have its own page 4, position 1, stored in its own files. The table
name picks the files, and (page, position) picks the spot inside them.
Keep that address shape in mind; indexes are built entirely out of it.

### What does reading and writing a page look like in code? {#what-does-reading-and-writing-a-page-look-like-in-code}

There is no special disk API for databases. Reading or writing a page is
ordinary file I/O, and it needs just two things: which file, and the byte
offset where the page starts inside that file.

That brings one more design choice: we don't let a file grow forever.
Each file holds **2 pages**, and a table's files are named after it:
`students.0`, `students.1`, and so on. A small helper,
`locate(table, page)`, turns a page number into that filename and offset.
We'll look at its arithmetic once the table has grown into a few files;
for now, take it as given.

Reading a page is then a seek and a read:

```python
def read_page(table, page):
    file, offset = locate(table, page)
    with open(file, "rb") as f:
        f.seek(offset)
        return f.read(PAGE_SIZE)
```

`seek` moves to the first byte of the page, and `read(PAGE_SIZE)` asks the
OS for the next 100 bytes. What comes back is raw bytes. The OS has no
idea it just returned two student rows; making sense of them is the
engine's job.

Writing goes the other way, with one extra concern: the bytes have to
actually reach the disk before the write counts as done.

```python
def write_page(table, page, data):
    file, offset = locate(table, page)
    mode = "r+b" if os.path.exists(file) else "w+b"
    with open(file, mode) as f:
        f.seek(offset)
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
```

`write` only copies the bytes into Python's own buffer. `flush` hands
them from that buffer to the OS, which may still keep them in memory for
a while. `os.fsync` tells the OS to put them on the disk and waits until
it has. The `mode` line just creates the file the first time a page lands
in it.

That is the entire contract with the OS: a filename, an offset, and 100
bytes going in or coming out. Everything else in this post, tables,
indexes, inserts, lookups, is code that decides *which page* to pass to
these two functions and what the bytes inside mean.

## What happens as the table grows? {#what-happens-as-the-table-grows}

Rows arrive one at a time, and the engine puts each one into the last page
that still has room. When there's no room, it starts a new page at the end.

### Why does a 10-row table end up in three files? {#why-does-a-10-row-table-end-up-in-three-files}

Insert ten students, in this order:

```
id  name    email
1   Asha    asha@x.com
2   Bala    bala@x.com
3   Zoya    zoya@x.com
4   Chen    chen@x.com
5   Ravi    ravi@x.com
6   Esha    esha@x.com
7   Mani    mani@x.com
8   Gita    gita@x.com
9   Kiran   kiran@x.com
10  Lata    lata@x.com
```

Remember the file naming: the table's name plus a file number, so the
students table lives in `students.0`, then `students.1`, and so on. Asha
and Bala fill page 0. Zoya and Chen fill page 1. Both
pages are in the first file, `students.0`, which now holds its 2 pages and
is full. Ravi needs a new page, page 2, so the engine starts the second
file, `students.1`. By the time Lata arrives:

```
students.0 → page 0: Asha, Bala      page 1: Zoya, Chen
students.1 → page 2: Ravi, Esha      page 3: Mani, Gita
students.2 → page 4: Kiran, Lata
```

10 rows at 2 per page is 5 pages; 5 pages at 2 per file is 3 files.

Notice the order: rows sit in **arrival order**, nothing else. This kind
of row storage is called a heap. It's not sorted by id, name, or email.
Id happens to line up with arrival here only because ids were handed out
in order. Any sorted view of this data has to be built separately, and
that's exactly what an index is.

### How does a page number turn into a file and an offset? {#how-does-a-page-number-turn-into-a-file-and-an-offset}

The engine numbers pages across the whole table as if it were one long
file: pages 0 to 4, with no gaps. The files are just that long numbering
chopped into pieces of 2 pages. So turning a page number back into a
place on disk is two lines of arithmetic, which is all `locate` does:

```python
PAGE_SIZE = 100
PAGES_PER_FILE = 2

def locate(table, page):
    file = f"{table}.{page // PAGES_PER_FILE}"
    offset = (page % PAGES_PER_FILE) * PAGE_SIZE
    return file, offset
```

Dividing by 2 says which file the page falls in. The remainder says how
many pages to skip inside that file, and multiplying by 100 turns that
into bytes. Try it on two pages from our table:

```
page 4 → file  4 // 2 = 2   → students.2
       → offset (4 % 2) × 100 = 0   → the first page in that file

page 3 → file  3 // 2 = 1   → students.1
       → offset (3 % 2) × 100 = 100 → the second page in that file
```

This is why the rest of the engine never needs to mention files at all.
An address like `(page 4, position 0)` is enough; the file and byte
offset fall out of the arithmetic.

## Where does an index live? {#where-does-an-index-live}

In its own files, made of the same 100-byte pages, read and written with
the same `read_page` and `write_page`. An index on `id` lives in
`students_id_idx.0`, `students_id_idx.1`, and so on.

### Isn't an index just another table? {#isnt-an-index-just-another-table}

Yes. Strip away the tree and an index on `id` is a two-column table: the
key, and the address of the row.

```
id → (page, position)
1  → (0, 0)        6  → (2, 1)
2  → (0, 1)        7  → (3, 0)
3  → (1, 0)        8  → (3, 1)
4  → (1, 1)        9  → (4, 0)
5  → (2, 0)        10 → (4, 1)
```

The difference from the heap is that these entries are kept **sorted by
key** and arranged as a B+ tree. Index entries are small, so say an index
page holds 4 of them. The entries fill three **leaf pages**, and one
**root page** on top says which leaf covers which keys:

```
students_id_idx.0 → page 0 (root): 1 → page 1 │ 5 → page 2 │ 9 → page 3
                    page 1 (leaf): 1, 2, 3, 4
students_id_idx.1 → page 2 (leaf): 5, 6, 7, 8
                    page 3 (leaf): 9, 10
```

Same pages, same files-of-2-pages rule, same `locate` arithmetic. The only
new idea is what the bytes inside mean.

### Why does an index on email look so different from the table? {#why-does-an-index-on-email-look-so-different-from-the-table}

Because it's sorted by a key that has nothing to do with arrival order.
Build an index on `email` and its leaves come out alphabetical, each entry
pointing back to wherever that row happened to land in the heap:

```
students_email_idx
  page 0 (root): a–f → page 1 │ g–q → page 2 │ r–z → page 3
  page 1 (leaf): asha (0,0)  bala (0,1)  chen (1,1)  esha (2,1)
  page 2 (leaf): gita (3,1)  kiran (4,0) lata (4,1)  mani (3,0)
  page 3 (leaf): ravi (2,0)  zoya (1,0)
```

Zoya arrived third, so she sits in page 1 of the heap, but she's the very
last entry in the email index. The heap is a pile in arrival order; each
index is the same rows seen through one sorted key. Add a third index and
you get a third set of files, a third tree, and a third ordering, all
pointing into the same heap.

How do those entries get there in the first place? Two cases. If the
index is created when the table is empty, there's nothing to build: the
first leaf just fills up as rows arrive. If it's created after the rows
exist, the engine scans the heap pages top to bottom, reads every row,
and writes one entry per row into the new index in sorted order. Either
way, from then on the two stay in sync: every insert, update, or delete
writes the heap page and the matching index leaf in the same breath, the
same pattern we'll see in the update and delete examples below.

### How does a query find its row? {#how-does-a-query-find-its-row}

The engine keeps a catalog (itself just a table stored in pages) that
says: `students` lives in `students.*`, and its id index lives in
`students_id_idx.*` with its root at page 0. Now run
`SELECT * FROM students WHERE id = 9`:

1. `read_page("students_id_idx", 0)`: `locate` returns
   `("students_id_idx.0", 0)`, so it reads 100 bytes from byte `0` of
   that file. The root says keys from 9 up live in page 3.
2. `read_page("students_id_idx", 3)`: `locate` returns
   `("students_id_idx.1", 100)`, so it reads from byte `100`, the second
   page of that file. The leaf says `9 → (4, 0)`.

   Notice the shape of the walk so far: every pointer inside the tree
   meant "another page of this same tree", so both reads stayed inside
   the `students_id_idx` files. The descent always ends at a leaf, and
   the leaf is where the tree stops pointing at itself. What it hands
   back, `9 → (4, 0)`, is no longer an index page but a row address in
   the heap.

   Notice also what that entry doesn't say: it has no file name and no
   table name, just a page and a position. It doesn't need them. The
   catalog already told the engine that `students_id_idx` is the index
   of the `students` table, so every row address in it points into the
   students heap. Now that the tree walk is over, the engine switches
   from the index's files to `students` itself, and `locate` works out
   which of its files page 4 is in.
3. `read_page("students", 4)`: `locate` returns `("students.2", 0)`, so
   it reads from byte `0` of that file. Position 0 of that page is
   Kiran's row.

Three page reads, each one a filename, an offset, and 100 bytes from the
OS. The tree only decided which page to ask for next. Without the index,
the engine would have to read all 5 heap pages across all 3 files and
check every row.

## What happens when rows change? {#what-happens-when-rows-change}

Every change follows the same shape: find the page, change its bytes in
memory, write the whole page back with `write_page`. Nothing ever shifts
other pages around.

### What do UPDATE and DELETE touch? {#what-do-update-and-delete-touch}

**Update Kiran's department.** Find her through the id index exactly as
above. Her address is `(4, 0)`: page 4, position 0, the first row on
page 4. `locate` puts page 4 at byte 0 of `students.2`. The engine reads
that page, changes her bytes at position 0, and writes the page back to
the same file and byte. One page rewritten. Indexes don't change, because
neither her id nor her email moved.

**Delete Ravi (id 5).** The id index gives his address as `(2, 0)`:
page 2, position 0, the first row on page 2. `locate` puts page 2 at
byte 0 of `students.1`. The engine reads that page, marks position 0 as
empty, and writes the page back. Esha stays at position 1; nothing slides
up to fill the hole, and a later insert can reuse it.

Then every index has to forget him, and each index entry lives on a page
of its own:

- In the id index, `5` sits on leaf page 2, which `locate` puts at byte 0
  of `students_id_idx.1`. Remove the entry, write the page back.
- In the email index, `ravi` sits on leaf page 3, at byte 100 of
  `students_email_idx.1`. Remove the entry, write the page back.

A delete touches the heap page plus one leaf page per index.

### What happens when an insert lands in the middle? {#what-happens-when-an-insert-lands-in-the-middle}

Insert a new student, **Dev, id 11, dev@x.com**. That's three writes:
one in the heap, one in each index. The first two are easy.

**The heap.** Page 4, the last page, already holds Kiran and Lata, so the
engine starts page 5. `locate` puts it in the empty second half of
`students.2`:

```
students.2
  byte 0    page 4: Kiran, Lata     (full)
  byte 100  page 5: Dev             ← new; Dev's address is (5, 0)
```

Our simple rule only looks at the last page, so it doesn't notice the
hole Ravi left on page 2. Real engines keep a record of free space so
they can reuse holes like that.

**The id index.** Id 11 is the largest id, so it goes at the end, on leaf
page 3. That page holds only 9 and 10, so there's room: add
`11 → (5, 0)` and write the page back.

**The email index.** This is the interesting one. Here's the index before
the insert (**Ravi is already gone from page 3**):

```
students_email_idx.0   page 0 (root)   a–f → 1 │ g–q → 2 │ r–z → 3
                       page 1 (leaf)   asha  bala  chen  esha    ← full
students_email_idx.1   page 2 (leaf)   gita  kiran  lata  mani
                       page 3 (leaf)   zoya
```

Alphabetically, `dev` goes between `chen` and `esha`. The root says
a–f lives on page 1, so that's where it belongs, in the **middle** of
the index. But page 1 already holds 4 entries. There's no room, so the
engine **splits** it in three steps:

1. **Keep the first half where it is.** asha, bala, and chen stay on
   page 1.
2. **Put the second half on a new page.** dev and esha go to a brand-new
   page. A file can't open up space in the middle without rewriting
   everything after it, so the new page can't sit next to page 1. It goes
   **at the end**: it becomes page 4, which `locate` puts at byte 0 of a
   new file, `students_email_idx.2`.
3. **Tell the root.** The root's a–f range now splits into a–c on page 1
   and d–f on page 4.

After the insert:

```
students_email_idx.0   page 0 (root)   a–c → 1 │ d–f → 4 │ g–q → 2 │ r–z → 3
                       page 1 (leaf)   asha  bala  chen
students_email_idx.1   page 2 (leaf)   gita  kiran  lata  mani
                       page 3 (leaf)   zoya
students_email_idx.2   page 4 (leaf)   dev  esha                  ← new, at the end
```

Now read the leaf pages two ways:

```
in the files, front to back:   page 1 → page 2 → page 3 → page 4   (order created)
in the root, left to right:    page 1 → page 4 → page 2 → page 3   (sorted order)
```

Page 4 is last in the files but second in the tree. That's the whole
trick: the root holds the sorted order, so the files never have to. The
files are only a place to put pages.

Those three steps are also the entire balancing act of a B+ tree. There's
no rotating or rearranging of nodes the way binary search trees do.
Whenever a page overflows, the same split applies: divide the entries,
add the new page at the same level, push a new range up into the root.
Every insert, update, or delete in any index runs this same machinery,
splitting when pages overflow and doing the mirror image when they empty
out. Notice what does none of it: the heap. No ranges, no splits, no
balancing, because nothing is ever searched there. The heap is only a
pile of rows; order is entirely the tree's job.

One more thing the split quietly bought: page 1 now has room for another
entry. The next insert in the a–c range just slides in, one page rewrite,
no split. And unlike Ravi's hole in the heap, esha left no hole behind:
nobody outside the tree points at an entry's position inside an index
page, so page 1 was rewritten with its three entries packed together and
plain free space after them. That's the payoff of splitting roughly in
half: both pages have room, most inserts stay cheap, and splits get rarer
as the tree grows.

---

We started with a grid of rows and asked where it actually lives on disk.
After following ten students all the way down, the answer is two
functions: `read_page` and `write_page`. A page number becomes a filename
and an offset, the OS moves 100 bytes, and the engine decides what those
bytes mean.

Everything else is a rule for choosing the next page number. The heap
says "the last page with room." The B+ tree says "follow the root to the
right leaf." A split says "add a page at the end and point to it." That's
why finding Kiran took three reads instead of five, why deleting Ravi
left a hole instead of moving rows, and why Dev's page can sit in the
middle of the tree and at the end of the files at the same time.

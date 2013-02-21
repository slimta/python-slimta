
.. include:: /global.rst

slimta Terminology
==================

To get started working with |slimta|, there are a few terms to know. Someone
familiar with SMTP and email servers will recognize many of them.

--------------

*MTA*
   Mail Transfer Agent. This is a server application used to transfer email
   messages from a source to a destination along a series of hops.

*MSA*
   Mail Submission Agent. This is a form of *MTA* that specializes in receiving
   email from a user's client application, like Mozilla Thunderbird or Apple
   Mail.

*MDA*
   Mail Delivery Agent. This is a form of *MTA* that specializes in being the
   final destination of a message: placing it in long-term storage, such as for
   access/download by IMAP or POP3.

*Edge*
   This is a function of the *MTA* that receives email messages from the
   outside, generally by listening on a socket and receiving connections.

*Queue*
   SMTP RFCs require *MTAs* to write email messages to persistent storage before
   acknowledging to the sender that the message has been received. The *queue*
   also takes responsibility for requesting delivery retries.

*Relay*
   This is a function of the *MTA* that attempts to transfer the email message
   either to another *MTA* or into long-term storage if acting as an *MDA*.

*MX*
   MX records are special DNS records used by SMTP to figure out where to
   deliver a message. MX records are prioritized such that lower-numbers are
   higher priority.

*Headers*
   Key-value data providing diagnostic information about an email's various hops
   from source to destination, as well as information to help present the email
   message to the user, such as who it was from and the subject.

*Bounce*
   Once an email is accepted by the sender's *MSA*, the sender's client has no
   way of knowing whether the message made it to its destination. If a message
   fails delivery in some *MTA*, that *MTA* will send a new email message back
   to the sender describing why the message failed.

*TLS*
   Encryption between an SMTP client and an SMTP server is done with *TLS*, a
   system for encryption and validation of a socket session. *TLS* usually
   starts when the client says ``STARTTLS``, but it is still common for *MTAs*
   to have special ports that encrypt the entire session.

*Authentication*
   To prevent unauthorized message delivery, many *MSAs* allow (and often
   require) user clients to present their identity (a username) with a shared
   secret (a password). The *MSA* will announce which authentication mechanisms
   it supports, and plaintext mechanisms may not be allowed unless the socket
   session is encrypted.

*Policies*
   A policy in an *MTA* is any behavior outside the standard receive, queue, and
   deliver behaviors. Authentication and encryption are good examples of
   standardized, universal policies. Examples of more customized policies could
   be forms of spam filtering, inclusion or filtering of custom headers, or
   smart forms of routing not based on *MX* records.


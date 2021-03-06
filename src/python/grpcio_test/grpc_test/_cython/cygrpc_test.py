# Copyright 2015, Google Inc.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met:
#
#     * Redistributions of source code must retain the above copyright
# notice, this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above
# copyright notice, this list of conditions and the following disclaimer
# in the documentation and/or other materials provided with the
# distribution.
#     * Neither the name of Google Inc. nor the names of its
# contributors may be used to endorse or promote products derived from
# this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import time
import unittest

from grpc._cython import cygrpc
from grpc_test._cython import test_utilities


class TypeSmokeTest(unittest.TestCase):

  def testStringsInUtilitiesUpDown(self):
    self.assertEqual(0, cygrpc.StatusCode.ok)
    metadatum = cygrpc.Metadatum('a', 'b')
    self.assertEqual('a'.encode(), metadatum.key)
    self.assertEqual('b'.encode(), metadatum.value)
    metadata = cygrpc.Metadata([metadatum])
    self.assertEqual(1, len(metadata))
    self.assertEqual(metadatum.key, metadata[0].key)

  def testMetadataIteration(self):
    metadata = cygrpc.Metadata([
        cygrpc.Metadatum('a', 'b'), cygrpc.Metadatum('c', 'd')])
    iterator = iter(metadata)
    metadatum = next(iterator)
    self.assertIsInstance(metadatum, cygrpc.Metadatum)
    self.assertEqual(metadatum.key, 'a'.encode())
    self.assertEqual(metadatum.value, 'b'.encode())
    metadatum = next(iterator)
    self.assertIsInstance(metadatum, cygrpc.Metadatum)
    self.assertEqual(metadatum.key, 'c'.encode())
    self.assertEqual(metadatum.value, 'd'.encode())
    with self.assertRaises(StopIteration):
      next(iterator)

  def testOperationsIteration(self):
    operations = cygrpc.Operations([
        cygrpc.operation_send_message('asdf')])
    iterator = iter(operations)
    operation = next(iterator)
    self.assertIsInstance(operation, cygrpc.Operation)
    # `Operation`s are write-only structures; can't directly debug anything out
    # of them. Just check that we stop iterating.
    with self.assertRaises(StopIteration):
      next(iterator)

  def testTimespec(self):
    now = time.time()
    timespec = cygrpc.Timespec(now)
    self.assertAlmostEqual(now, float(timespec), places=8)

  def testCompletionQueueUpDown(self):
    completion_queue = cygrpc.CompletionQueue()
    del completion_queue

  def testServerUpDown(self):
    server = cygrpc.Server(cygrpc.ChannelArgs([]))
    del server

  def testChannelUpDown(self):
    channel = cygrpc.Channel('[::]:0', cygrpc.ChannelArgs([]))
    del channel

  @unittest.skip('TODO(atash): undo skip after #2229 is merged')
  def testServerStartNoExplicitShutdown(self):
    server = cygrpc.Server()
    completion_queue = cygrpc.CompletionQueue()
    server.register_completion_queue(completion_queue)
    port = server.add_http2_port('[::]:0')
    self.assertIsInstance(port, int)
    server.start()
    del server

  @unittest.skip('TODO(atash): undo skip after #2229 is merged')
  def testServerStartShutdown(self):
    completion_queue = cygrpc.CompletionQueue()
    server = cygrpc.Server()
    server.add_http2_port('[::]:0')
    server.register_completion_queue(completion_queue)
    server.start()
    shutdown_tag = object()
    server.shutdown(completion_queue, shutdown_tag)
    event = completion_queue.poll()
    self.assertEqual(cygrpc.CompletionType.operation_complete, event.type)
    self.assertIs(shutdown_tag, event.tag)
    del server
    del completion_queue


class InsecureServerInsecureClient(unittest.TestCase):

  def setUp(self):
    self.server_completion_queue = cygrpc.CompletionQueue()
    self.server = cygrpc.Server()
    self.server.register_completion_queue(self.server_completion_queue)
    self.port = self.server.add_http2_port('[::]:0')
    self.server.start()
    self.client_completion_queue = cygrpc.CompletionQueue()
    self.client_channel = cygrpc.Channel('localhost:{}'.format(self.port))

  def tearDown(self):
    del self.server
    del self.client_completion_queue
    del self.server_completion_queue

  def testEcho(self):
    DEADLINE = time.time()+5
    DEADLINE_TOLERANCE = 0.25
    CLIENT_METADATA_ASCII_KEY = b'key'
    CLIENT_METADATA_ASCII_VALUE = b'val'
    CLIENT_METADATA_BIN_KEY = b'key-bin'
    CLIENT_METADATA_BIN_VALUE = b'\0'*1000
    SERVER_INITIAL_METADATA_KEY = b'init_me_me_me'
    SERVER_INITIAL_METADATA_VALUE = b'whodawha?'
    SERVER_TRAILING_METADATA_KEY = b'California_is_in_a_drought'
    SERVER_TRAILING_METADATA_VALUE = b'zomg it is'
    SERVER_STATUS_CODE = cygrpc.StatusCode.ok
    SERVER_STATUS_DETAILS = b'our work is never over'
    REQUEST = b'in death a member of project mayhem has a name'
    RESPONSE = b'his name is robert paulson'
    METHOD = b'twinkies'
    HOST = b'hostess'

    cygrpc_deadline = cygrpc.Timespec(DEADLINE)

    server_request_tag = object()
    request_call_result = self.server.request_call(
        self.server_completion_queue, self.server_completion_queue,
        server_request_tag)

    self.assertEqual(cygrpc.CallError.ok, request_call_result)

    client_call_tag = object()
    client_call = self.client_channel.create_call(self.client_completion_queue,
                                                  METHOD, HOST, cygrpc_deadline)
    client_initial_metadata = cygrpc.Metadata([
        cygrpc.Metadatum(CLIENT_METADATA_ASCII_KEY,
                         CLIENT_METADATA_ASCII_VALUE),
        cygrpc.Metadatum(CLIENT_METADATA_BIN_KEY, CLIENT_METADATA_BIN_VALUE)])
    client_start_batch_result = client_call.start_batch(cygrpc.Operations([
        cygrpc.operation_send_initial_metadata(client_initial_metadata),
        cygrpc.operation_send_message(REQUEST),
        cygrpc.operation_send_close_from_client(),
        cygrpc.operation_receive_initial_metadata(),
        cygrpc.operation_receive_message(),
        cygrpc.operation_receive_status_on_client()
    ]), client_call_tag)
    self.assertEqual(cygrpc.CallError.ok, client_start_batch_result)
    client_event_future = test_utilities.CompletionQueuePollFuture(
        self.client_completion_queue, cygrpc_deadline)

    request_event = self.server_completion_queue.poll(cygrpc_deadline)
    self.assertEqual(cygrpc.CompletionType.operation_complete,
                      request_event.type)
    self.assertIsInstance(request_event.operation_call, cygrpc.Call)
    self.assertIs(server_request_tag, request_event.tag)
    self.assertEqual(0, len(request_event.batch_operations))
    self.assertEqual(dict(client_initial_metadata),
                      dict(request_event.request_metadata))
    self.assertEqual(METHOD, request_event.request_call_details.method)
    self.assertEqual(HOST, request_event.request_call_details.host)
    self.assertLess(
        abs(DEADLINE - float(request_event.request_call_details.deadline)),
        DEADLINE_TOLERANCE)

    server_call_tag = object()
    server_call = request_event.operation_call
    server_initial_metadata = cygrpc.Metadata([
        cygrpc.Metadatum(SERVER_INITIAL_METADATA_KEY,
                         SERVER_INITIAL_METADATA_VALUE)])
    server_trailing_metadata = cygrpc.Metadata([
        cygrpc.Metadatum(SERVER_TRAILING_METADATA_KEY,
                         SERVER_TRAILING_METADATA_VALUE)])
    server_start_batch_result = server_call.start_batch([
        cygrpc.operation_send_initial_metadata(server_initial_metadata),
        cygrpc.operation_receive_message(),
        cygrpc.operation_send_message(RESPONSE),
        cygrpc.operation_receive_close_on_server(),
        cygrpc.operation_send_status_from_server(
            server_trailing_metadata, SERVER_STATUS_CODE, SERVER_STATUS_DETAILS)
    ], server_call_tag)
    self.assertEqual(cygrpc.CallError.ok, server_start_batch_result)

    client_event = client_event_future.result()
    server_event = self.server_completion_queue.poll(cygrpc_deadline)

    self.assertEqual(6, len(client_event.batch_operations))
    found_client_op_types = set()
    for client_result in client_event.batch_operations:
      # we expect each op type to be unique
      self.assertNotIn(client_result.type, found_client_op_types)
      found_client_op_types.add(client_result.type)
      if client_result.type == cygrpc.OperationType.receive_initial_metadata:
        self.assertEqual(dict(server_initial_metadata),
                         dict(client_result.received_metadata))
      elif client_result.type == cygrpc.OperationType.receive_message:
        self.assertEqual(RESPONSE, client_result.received_message.bytes())
      elif client_result.type == cygrpc.OperationType.receive_status_on_client:
        self.assertEqual(dict(server_trailing_metadata),
                         dict(client_result.received_metadata))
        self.assertEqual(SERVER_STATUS_DETAILS,
                         client_result.received_status_details)
        self.assertEqual(SERVER_STATUS_CODE, client_result.received_status_code)
    self.assertEqual(set([
          cygrpc.OperationType.send_initial_metadata,
          cygrpc.OperationType.send_message,
          cygrpc.OperationType.send_close_from_client,
          cygrpc.OperationType.receive_initial_metadata,
          cygrpc.OperationType.receive_message,
          cygrpc.OperationType.receive_status_on_client
      ]), found_client_op_types)

    self.assertEqual(5, len(server_event.batch_operations))
    found_server_op_types = set()
    for server_result in server_event.batch_operations:
      self.assertNotIn(client_result.type, found_server_op_types)
      found_server_op_types.add(server_result.type)
      if server_result.type == cygrpc.OperationType.receive_message:
        self.assertEqual(REQUEST, server_result.received_message.bytes())
      elif server_result.type == cygrpc.OperationType.receive_close_on_server:
        self.assertFalse(server_result.received_cancelled)
    self.assertEqual(set([
          cygrpc.OperationType.send_initial_metadata,
          cygrpc.OperationType.receive_message,
          cygrpc.OperationType.send_message,
          cygrpc.OperationType.receive_close_on_server,
          cygrpc.OperationType.send_status_from_server
      ]), found_server_op_types)

    del client_call
    del server_call


if __name__ == '__main__':
  unittest.main(verbosity=2)

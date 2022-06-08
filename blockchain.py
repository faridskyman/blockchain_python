import sys
import hashlib
import json

from time import time
from urllib import response
from uuid import uuid4
from flask import Flask, jsonify, request
from more_itertools import last
from numpy import block
import requests
from urllib.parse import urlparse

class Blockchain(object):
    difficulty_target = "0000"

    def hash_block(self, block):
        block_encoded = json.dumps(block, sort_keys=True).encode()
        return hashlib.sha256(block_encoded).hexdigest()

    def __init__(self):
        #nodes setup
        self.nodes =set()
        
        self.chain = []
        self.current_transactions = []
        genesis_hash = self.hash_block("genesis_block")
        self.append_block(hash_of_previous_block = genesis_hash, 
            nounce = self.proof_of_work(0, genesis_hash, [])
            )
        
    def proof_of_work(self, index, hash_of_previous_block, transactons):
        nounce = 0
        while self.validate_proof(index, hash_of_previous_block, transactons, nounce) is False:
            nounce +=1
        return nounce

    def validate_proof(self, index, hash_of_previous_block, transactons, nounce):
        content = f'{index}{hash_of_previous_block}{transactons}{nounce}'.encode()
        content_hash = hashlib.sha256(content).hexdigest()
        return content_hash[:len(self.difficulty_target)] == self.difficulty_target

    def append_block(self, nounce, hash_of_previous_block):
        block ={
            'index': len(self.chain),
            'timestamp': time(),
            'transactions': self.current_transactions,
            'nounce': nounce,
            'hash_of_previous_block': hash_of_previous_block
        }

        self.current_transactions = []
        self.chain.append(block)
        return block

    def add_transaction(self, sender, recipient, amount):
        self.current_transactions.append({
            'amount': amount,
            'recipient': recipient,
            'sender': sender,
        })
        return self.last_block['index'] + 1

    @property
    def last_block(self):
        return self.chain[-1]


    #add additional node
    def add_nodes(self, address):
        parsed_url = urlparse(address)
        self.nodes.add(parsed_url.netloc)
        print(parsed_url.netloc)

    #determine if a given blockchain is valid
    def validate_chain(self, chain):
        last_block = chain[0] #genesis block
        current_index = 1   #start with 2nd block

        while current_index < len(chain):
            block = chain[current_index]
            if block['hash_of_previous_block'] != self.hash_block(last_block):
                return False
            
            #check for valid nounce
            if not self.validate_proof(current_index,block['hash_of_previous_block'],block['transactions'],block['nounce']):
                return False
            
            #move to next block in the chain
            last_block = block
            current_index += 1
        
        return True

    def update_blockchain(self):
        #get nodes around us that has been registered
        neighbours = self.nodes
        new_chain = None

        #for for chain that is longer then ours
        max_length = len(self.chain)

        #grab and verify all nodes in the netowork
        for node in neighbours:
            #get the blockchain from other nodes
            response = requests.get(f'http://{node}/blockchain')
            if response.status_code == 200:
                length = response.json()['length']
                chain = response.json()['chain']

                #check if the length is longer and the chain is valid
                if length > max_length and self.validate_chain(chain):
                    max_length = length
                    new_chain = chain
            
            #replace our chain if we discovered a new, valid chan longer then ours
            if new_chain:
                self.chain = new_chain
                return True
            
            return False



# - - - WEB PART - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -#

app = Flask(__name__)
node_identifier = str(uuid4()).replace('-','')
blockchain = Blockchain()

@app.route('/blockchain', methods=['GET'])
def full_chain():
    response = {
        'chain': blockchain.chain,
        'length': len(blockchain.chain)
    }
    return jsonify(response), 200

@app.route('/mine', methods=['GET'])
def mine_block():
    blockchain.add_transaction(
        sender="0",
        recipient=node_identifier,
        amount=1
    )
    last_block_hash = blockchain.hash_block(blockchain.last_block)
    index = len(blockchain.chain)
    nounce = blockchain.proof_of_work(index, last_block_hash,blockchain.current_transactions)
    block = blockchain.append_block(nounce, last_block_hash)
    response = {
        'message': "New Block Mined",
        'index': block['index'],
        'hash_of_previous_block': block['hash_of_previous_block'],
        'nounce': block['nounce'],
        'transaction': block['transactions'],
    }
    return jsonify(response), 200

@app.route('/transaction/new', methods=['POST'])
def new_transaction():
    values = request.get_json()
    required_fields = ['sender', 'recipient', 'amount']
    if not all(k in values for k in required_fields):
        return('Missing fields', 400)
    index = blockchain.add_transaction(
        values['sender'],
        values['recipient'],
        values['amount']
    )

    response = {'message': f'Transaction will be added to the Block {index}'}
    return (jsonify(response), 201)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(sys.argv[1]))
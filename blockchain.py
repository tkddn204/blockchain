import hashlib
import json
from time import time
from urllib.parse import urlparse
from uuid import uuid4

import requests
from flask import Flask, jsonify, request


class Blockchain:
    def __init__(self):
        self.current_transactions = []
        self.chain = []
        self.nodes = set()

        # Create the genesis block
        self.new_block(previous_hash='1', proof=100)

    def register_node(self, address):
        """
        노드의 리스트에 새로운 노드를 추가합니다.

        :param address: 노드의 주소입니다. (예: http://192.168.0.5:5000)
        """

        parsed_url = urlparse(address)
        self.nodes.add(parsed_url.netloc)

    def valid_chain(self, chain):
        """
        주어진 블록체인이 유효한지 체크합니다.

        :param chain: 블록체인
        :return: 유효하면 True, 아니면 False
        """

        last_block = chain[0]
        current_index = 1

        while current_index < len(chain):
            block = chain[current_index]
            print(f'{last_block}')
            print(f'{block}')
            print("\n-----------\n")
            # Check that the hash of the block is correct
            if block['previous_hash'] != self.hash(last_block):
                return False

            # Check that the Proof of Work is correct
            if not self.valid_proof(last_block['proof'], block['proof']):
                return False

            last_block = block
            current_index += 1

        return True

    def resolve_conflicts(self):
        """
        이것은 우리의 '합의 알고리즘' 입니다.
        네트워크에서 가장 긴 체인으로 교체함으로써 충돌을 해결합니다.

        :return: 재배치가 되면 True, 되지 않았으면 False
        """

        neighbours = self.nodes
        new_chain = None

        # 우리는 우리의 체인보다 긴 체인들을 찾아야 합니다.
        max_length = len(self.chain)

        # 네트워크에서 모든 노드들로부터 체인들을 잡고 검증해야 합니다.
        for node in neighbours:
            response = requests.get(f'http://{node}/chain')

            if response.status_code == 200:
                length = response.json()['length']
                chain = response.json()['chain']

                # 길이가 더 긴지 아닌지, 체인이 유효한지를 체크합니다.
                if length > max_length and self.valid_chain(chain):
                    max_length = length
                    new_chain = chain

        # 새로운 우리 것보다 더 길고 유효한 체인을 발견하면 체인을 재배치합니다.
        if new_chain:
            self.chain = new_chain
            return True

        return False

    def new_block(self, proof, previous_hash):
        """
        블록체인에서 새로운 블록을 만듭니다.

        :param proof: '작업증명 알고리즘'에 의해 주어지는 증명
        :param previous_hash: 이전 블록의 해쉬값
        :return: 새로운 블록을 반환합니다.
        """

        block = {
            'index': len(self.chain) + 1,
            'timestamp': time(),
            'transactions': self.current_transactions,
            'proof': proof,
            'previous_hash': previous_hash or self.hash(self.chain[-1]),
        }

        # 트랜잭션들의 현재 리스트를 리셋합니다.
        self.current_transactions = []

        self.chain.append(block)
        return block

    def new_transaction(self, sender, recipient, amount):
        """
        다음 채굴된 블록으로 들어가는 새로운 트랜잭션을 만듭니다.

        :param sender: 송신자의 주소
        :param recipient: 수령인의 주소
        :param amount: 금액
        :return: 이 트랜잭션을 '보류할' 블록의 인덱스를 반환합니다.
        """
        self.current_transactions.append({
            'sender': sender,
            'recipient': recipient,
            'amount': amount,
        })

        return self.last_block['index'] + 1

    @property
    def last_block(self):
        return self.chain[-1]

    @staticmethod
    def hash(block):
        """
        블록의 SHA-256 해쉬값을 만듭니다.

        :param block: 블록
        """

        # 우리는 JSON이 '순서대로인지'를 확실히 해야만 합니다.
        # 확실히 하지 않으면 일치하지 않는 해쉬가 생길 겁니다.
        block_string = json.dumps(block, sort_keys=True).encode()
        return hashlib.sha256(block_string).hexdigest()

    def proof_of_work(self, last_proof):
        """
        간단한 작업증명 알고리즘:
         - 해쉬(pp')가 4개의 0을 포함하도록 하는 숫자 p'를 찾습니다. 여기서 p는 이전의 p'입니다.
         - p는 이전의 '증명'이며, p'는 새로운 '증명'입니다.
        """

        proof = 0
        while self.valid_proof(last_proof, proof) is False:
            proof += 1

        return proof

    @staticmethod
    def valid_proof(last_proof, proof):
        """
        증명의 유효성을 판단합니다.

        :param last_proof: 이전 증명
        :param proof: 현재 증명
        :return: 맞으면 True, 틀리면 False
        """

        guess = f'{last_proof}{proof}'.encode()
        guess_hash = hashlib.sha256(guess).hexdigest()
        return guess_hash[:4] == "0000"


# 노드 객체화(플라스크 객체)
app = Flask(__name__)

# 이 노드에서 전역으로 유일한 주소값을 생성합니다.
node_identifier = str(uuid4()).replace('-', '')

# 블록체인 객체화
blockchain = Blockchain()


@app.route('/mine', methods=['GET'])
def mine():
    # 우리는 다음 증명을 얻기 위해서 작업 증명 알고리즘을 돌려야합니다.
    last_block = blockchain.last_block
    last_proof = last_block['proof']
    proof = blockchain.proof_of_work(last_proof)

    # 우리는 증명을 찾아내는 보상을 받아야 합니다.
    # 송신자는 이 노드가 새로운 코인을 채굴했음을 알리는 "0" 입니다.
    blockchain.new_transaction(
        sender="0",
        recipient=node_identifier,
        amount=1,
    )

    # 새로운 블록을 체인에 추가하여 구축합니다.
    previous_hash = blockchain.hash(last_block)
    block = blockchain.new_block(proof, previous_hash)

    response = {
        'message': "New Block Forged",
        'index': block['index'],
        'transactions': block['transactions'],
        'proof': block['proof'],
        'previous_hash': block['previous_hash'],
    }
    return jsonify(response), 200


@app.route('/transactions/new', methods=['POST'])
def new_transaction():
    values = request.get_json()

    # 요구하는 필드들이 POST 데이터에 있는지 체크합니다.
    required = ['sender', 'recipient', 'amount']
    if not all(k in values for k in required):
        return '값이 존재하지 않습니다.', 400

    # 새로운 트랜잭션을 만듭니다.
    index = blockchain.new_transaction(values['sender'], values['recipient'], values['amount'])

    response = {'message': f'트랜잭션이 {index}번 블록에 추가될 것입니다.'}
    return jsonify(response), 201


@app.route('/chain', methods=['GET'])
def full_chain():
    response = {
        'chain': blockchain.chain,
        'length': len(blockchain.chain),
    }
    return jsonify(response), 200


@app.route('/nodes/register', methods=['POST'])
def register_nodes():
    values = request.get_json()

    nodes = values.get('nodes')
    if nodes is None:
        return "에러 : 노드들의 유효한 리스트를 공급해주세요.", 400

    for node in nodes:
        blockchain.register_node(node)

    response = {
        'message': '새로운 노드들이 추가되었습니다.',
        'total_nodes': list(blockchain.nodes),
    }
    return jsonify(response), 201


@app.route('/nodes/resolve', methods=['GET'])
def consensus():
    replaced = blockchain.resolve_conflicts()

    if replaced:
        response = {
            'message': '블록체인이 재배치되었습니다.',
            'new_chain': blockchain.chain
        }
    else:
        response = {
            'message': '우리 블록체인은 강한 권한을 가지고 있습니다.',
            'chain': blockchain.chain
        }

    return jsonify(response), 200


if __name__ == '__main__':
    from argparse import ArgumentParser

    parser = ArgumentParser()
    parser.add_argument('-p', '--port', default=5000, type=int, help='port to listen on')
    args = parser.parse_args()
    port = args.port

    app.run(host='0.0.0.0', port=port)

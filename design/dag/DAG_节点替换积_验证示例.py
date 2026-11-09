"""验证原始节点替换积，以及 Workflow 的排除、桥接与传递约简。

依赖：Python 3、NetworkX。直接运行本文件执行全部断言。
"""

from itertools import combinations
from random import Random

import networkx as nx

def make(nodes,edges):
    g=nx.DiGraph()
    g.add_nodes_from(['S','T']+nodes)
    g.add_edges_from(edges)
    check(g)
    return g

def check(g):
    assert 'S' in g and 'T' in g
    assert nx.is_directed_acyclic_graph(g)
    assert g.in_degree('S')==0 and g.out_degree('T')==0
    assert ('S','T') not in g.edges
    internal=set(g)-{'S','T'}
    assert internal
    for n in internal:
        assert nx.has_path(g,'S',n) and nx.has_path(g,n,'T')

def prod(g,h):
    G=set(g)-{'S','T'}
    H=set(h)-{'S','T'}
    HI=set(h.successors('S'))
    HO=set(h.predecessors('T'))
    k=nx.DiGraph()
    k.add_nodes_from(['S','T'])
    k.add_nodes_from((u,v) for u in G for v in H)
    for u in G:
        for a,b in h.edges:
            if a in H and b in H:
                k.add_edge((u,a),(u,b))
    for u,v in g.edges:
        if u in G and v in G:
            for a in HO:
                for b in HI:
                    k.add_edge((u,a),(v,b))
        elif u=='S' and v in G:
            for b in HI:
                k.add_edge('S',(v,b))
        elif u in G and v=='T':
            for a in HO:
                k.add_edge((u,a),'T')
    check(k)
    return k

G=make(['A','B','C'],[('S','A'),('S','B'),('A','C'),('B','C'),('C','T')])
H=make(['p','q','r'],[('S','p'),('S','q'),('p','r'),('q','r'),('r','T')])
K=make(['i','j','k'],[('S','i'),('S','j'),('i','k'),('j','k'),('k','T')])
I=make(['e'],[('S','e'),('e','T')])
P=prod(G,H)
assert len(P)==11 and P.number_of_edges()==15
lhs=prod(P,K)
rhs=prod(G,prod(H,K))

def norm_lhs(n):
    return n if n in ('S','T') else (n[0][0],n[0][1],n[1])
def norm_rhs(n):
    return n if n in ('S','T') else (n[0],n[1][0],n[1][1])
assert {(norm_lhs(a),norm_lhs(b)) for a,b in lhs.edges}=={(norm_rhs(a),norm_rhs(b)) for a,b in rhs.edges}
assert nx.is_isomorphic(G,prod(G,I)) and nx.is_isomorphic(G,prod(I,G))
X=make(['a','b'],[('S','a'),('a','b'),('b','T')])
Y=make(['p','q'],[('S','p'),('S','q'),('p','T'),('q','T')])
assert prod(X,Y).number_of_edges()==8
assert prod(Y,X).number_of_edges()==6
print('P nodes/edges:',len(P),P.number_of_edges())
print('Assoc triple product verified: nodes/edges:',len(lhs),lhs.number_of_edges())
print('Identity verified; non-commutative witness: 8 vs 6 edges')


def bridge(g, excluded):
    """只沿原图穿过被排除节点，到第一个保留端点即停止。"""
    check(g)
    excluded = set(excluded)
    internal = set(g) - {'S', 'T'}
    if not excluded <= internal:
        raise ValueError('Only actual nodes can be excluded')
    if not internal - excluded:
        raise ValueError('Cannot exclude all actual nodes')

    result = g.subgraph(set(g) - excluded).copy()
    for source in result:
        pending = list(g.successors(source))
        visited = set()
        while pending:
            target = pending.pop()
            if target in visited:
                continue
            visited.add(target)
            if target in excluded:
                pending.extend(g.successors(target))
            else:
                result.add_edge(source, target)
    return result


def finalize(g, excluded=()):
    bridged = bridge(g, excluded)
    reduced = nx.transitive_reduction(bridged)
    # NetworkX 的约简不保留属性；来源 members、节点角色等必须保留。
    reduced.graph.update(bridged.graph)
    reduced.add_nodes_from(bridged.nodes(data=True))
    check(reduced)
    return reduced


def verify_final(g, excluded=()):
    result = finalize(g, excluded)
    assert set(result) == set(g) - set(excluded)
    assert dict(result.nodes(data=True)) == {
        n: data for n, data in g.nodes(data=True) if n in result
    }
    # 保留节点之间的每一对可达关系都不变，包括虚拟边界。
    for u in result:
        for v in result:
            assert nx.has_path(g, u, v) == nx.has_path(result, u, v)
    # 任一保留边均不可移除，否则至少丢失这一对端点的依赖顺序。
    for u, v in list(result.edges):
        without_edge = result.copy()
        without_edge.remove_edge(u, v)
        assert not nx.has_path(without_edge, u, v)
    return result


chain = make(
    ['A', 'x', 'B', 'y', 'C', 'z'],
    [('S', 'A'), ('A', 'x'), ('x', 'B'), ('B', 'y'),
     ('y', 'C'), ('A', 'z'), ('z', 'C'), ('C', 'T')],
)
chain.nodes['B']['members'] = {'feature': 'login', 'layer': 'domain'}
excluded = {'x', 'y', 'z'}
assert ('A', 'C') in bridge(chain, excluded).edges
expected = {('S', 'A'), ('A', 'B'), ('B', 'C'), ('C', 'T')}
assert set(verify_final(chain, excluded).edges) == expected
assert set(verify_final(chain, {'x', 'B', 'y', 'z'}).edges) == {
    ('S', 'A'), ('A', 'C'), ('C', 'T'),
}

# 无 exclude 也约简原有冗余边，含 start/end 的冗余连接。
redundant = make(
    ['A', 'B', 'C'],
    list(expected) + [('A', 'C'), ('S', 'B'), ('A', 'T')],
)
assert set(verify_final(redundant).edges) == expected

# 并行与汇聚：先补 domain→presentation，再删除这条冗余边。
layer = make(
    ['domain', 'application', 'data', 'presentation'],
    [('S', 'domain'), ('domain', 'application'), ('domain', 'data'),
     ('application', 'presentation'), ('data', 'presentation'),
     ('presentation', 'T')],
)
assert set(verify_final(layer).predecessors('presentation')) == {'application', 'data'}
assert ('domain', 'presentation') in bridge(layer, {'application'}).edges
assert set(verify_final(layer, {'application'}).edges) == {
    ('S', 'domain'), ('domain', 'data'), ('data', 'presentation'),
    ('presentation', 'T'),
}
# 验证最终约简与实际替换积的连接，保留 P 的原始边数断言。
verify_final(P, {('A', 'r'), ('B', 'p')})

# 删除整个并行分支可能临时生成 S→T，由全图约简删除。
parallel = make(['A', 'B'], [('S', 'A'), ('S', 'B'), ('A', 'T'), ('B', 'T')])
assert ('S', 'T') in bridge(parallel, {'A'}).edges
assert set(verify_final(parallel, {'A'}).edges) == {('S', 'B'), ('B', 'T')}

# 改变节点及边的插入顺序，进而改变桥接端点和候选边的遍历顺序。
rng = Random(17)
for _ in range(30):
    nodes = list(chain.nodes(data=True))
    edges = list(chain.edges)
    removed = list(excluded)
    rng.shuffle(nodes)
    rng.shuffle(edges)
    rng.shuffle(removed)
    shuffled = nx.DiGraph()
    shuffled.add_nodes_from(nodes)
    shuffled.add_edges_from(edges)
    assert set(verify_final(shuffled, removed).edges) == expected

for invalid in [set(chain) - {'S', 'T'}, {'S'}, {'T'}, {'unknown'}]:
    try:
        finalize(chain, invalid)
    except ValueError:
        pass
    else:
        raise AssertionError(f'Invalid exclusion accepted: {invalid}')

# 穷举至多四个实际节点的有序 DAG 及所有非空保留子集。
cases = 0
for count in range(1, 5):
    nodes = list(range(count))
    possible_edges = list(combinations(nodes, 2))
    for mask in range(1 << len(possible_edges)):
        edges = [edge for bit, edge in enumerate(possible_edges) if mask & (1 << bit)]
        sources = set(nodes) - {v for _, v in edges}
        sinks = set(nodes) - {u for u, _ in edges}
        original = make(nodes, edges + [('S', n) for n in sources] + [(n, 'T') for n in sinks])
        for excluded_mask in range((1 << count) - 1):
            removed = {n for n in nodes if excluded_mask & (1 << n)}
            verify_final(original, removed)
            cases += 1

print('Workflow exclusion/reduction verified: reachability, minimal edges, boundaries, attributes and order independence')
print('Exhaustive small-DAG cases:', cases)

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

# -*- coding: utf-8 -*-
#    Copyright (C) 2010 by
#    Aric Hagberg <hagberg@lanl.gov>
#    Dan Schult <dschult@colgate.edu>
#    Pieter Swart <swart@lanl.gov>
#    All rights reserved.
#    BSD license.
#
# Author:  Andrey Paramonov <paramon@acdlabs.ru>
""" Functions measuring similarity using graph edit distance.

The graph edit distance is the number of edge/node changes needed
to make two graphs isomorphic.

The default algorithm/implementation is sub-optimal for some graphs.
The problem of finding the exact Graph Edit Distance (GED) is NP-hard
so it is often slow. If the simple interface `graph_edit_distance`
takes too long for your graph, try `optimize_graph_edit_distance`
and/or `optimize_edit_paths`.

At the same time, I encourage capable people to investigate
alternative GED algorithms, in order to improve the choices available.
"""
from itertools import product
import math
import networkx as nx
from operator import *
import sys

__author__ = 'Andrey Paramonov <paramon@acdlabs.ru>'

__all__ = [
    'graph_edit_distance',
    'optimal_edit_paths',
    'optimize_graph_edit_distance',
    'optimize_edit_paths',
    'simrank_similarity',
    'simrank_similarity_numpy',
]


def debug_print(*args, **kwargs):
    print(*args, **kwargs)


def graph_edit_distance(G1, G2, node_match=None, edge_match=None,
                        node_subst_cost=None, node_del_cost=None,
                        node_ins_cost=None,
                        edge_subst_cost=None, edge_del_cost=None,
                        edge_ins_cost=None,
                        upper_bound=None):
    """Returns GED (graph edit distance) between graphs G1 and G2.

    Graph edit distance is a graph similarity measure analogous to
    Levenshtein distance for strings.  It is defined as minimum cost
    of edit path (sequence of node and edge edit operations)
    transforming graph G1 to graph isomorphic to G2.

    Parameters
    ----------
    G1, G2: graphs
        The two graphs G1 and G2 must be of the same type.

    node_match : callable
        A function that returns True if node n1 in G1 and n2 in G2
        should be considered equal during matching.

        The function will be called like

           node_match(G1.nodes[n1], G2.nodes[n2]).

        That is, the function will receive the node attribute
        dictionaries for n1 and n2 as inputs.

        Ignored if node_subst_cost is specified.  If neither
        node_match nor node_subst_cost are specified then node
        attributes are not considered.

    edge_match : callable
        A function that returns True if the edge attribute dictionaries
        for the pair of nodes (u1, v1) in G1 and (u2, v2) in G2 should
        be considered equal during matching.

        The function will be called like

           edge_match(G1[u1][v1], G2[u2][v2]).

        That is, the function will receive the edge attribute
        dictionaries of the edges under consideration.

        Ignored if edge_subst_cost is specified.  If neither
        edge_match nor edge_subst_cost are specified then edge
        attributes are not considered.

    node_subst_cost, node_del_cost, node_ins_cost : callable
        Functions that return the costs of node substitution, node
        deletion, and node insertion, respectively.

        The functions will be called like

           node_subst_cost(G1.nodes[n1], G2.nodes[n2]),
           node_del_cost(G1.nodes[n1]),
           node_ins_cost(G2.nodes[n2]).

        That is, the functions will receive the node attribute
        dictionaries as inputs.  The functions are expected to return
        positive numeric values.

        Function node_subst_cost overrides node_match if specified.
        If neither node_match nor node_subst_cost are specified then
        default node substitution cost of 0 is used (node attributes
        are not considered during matching).

        If node_del_cost is not specified then default node deletion
        cost of 1 is used.  If node_ins_cost is not specified then
        default node insertion cost of 1 is used.

    edge_subst_cost, edge_del_cost, edge_ins_cost : callable
        Functions that return the costs of edge substitution, edge
        deletion, and edge insertion, respectively.

        The functions will be called like

           edge_subst_cost(G1[u1][v1], G2[u2][v2]),
           edge_del_cost(G1[u1][v1]),
           edge_ins_cost(G2[u2][v2]).

        That is, the functions will receive the edge attribute
        dictionaries as inputs.  The functions are expected to return
        positive numeric values.

        Function edge_subst_cost overrides edge_match if specified.
        If neither edge_match nor edge_subst_cost are specified then
        default edge substitution cost of 0 is used (edge attributes
        are not considered during matching).

        If edge_del_cost is not specified then default edge deletion
        cost of 1 is used.  If edge_ins_cost is not specified then
        default edge insertion cost of 1 is used.

    upper_bound : numeric
        Maximum edit distance to consider.  Return None if no edit
        distance under or equal to upper_bound exists.

    Examples
    --------
    >>> G1 = nx.cycle_graph(6)
    >>> G2 = nx.wheel_graph(7)
    >>> nx.graph_edit_distance(G1, G2)
    7.0

    See Also
    --------
    optimal_edit_paths, optimize_graph_edit_distance,

    is_isomorphic (test for graph edit distance of 0)

    References
    ----------
    .. [1] Zeina Abu-Aisheh, Romain Raveaux, Jean-Yves Ramel, Patrick
       Martineau. An Exact Graph Edit Distance Algorithm for Solving
       Pattern Recognition Problems. 4th International Conference on
       Pattern Recognition Applications and Methods 2015, Jan 2015,
       Lisbon, Portugal. 2015,
       <10.5220/0005209202710278>. <hal-01168816>
       https://hal.archives-ouvertes.fr/hal-01168816

    """
    bestcost = None
    for vertex_path, edge_path, cost in \
        optimize_edit_paths(G1, G2, node_match, edge_match,
                            node_subst_cost, node_del_cost, node_ins_cost,
                            edge_subst_cost, edge_del_cost, edge_ins_cost,
                            upper_bound, True):
        #assert bestcost is None or cost < bestcost
        bestcost = cost
    return bestcost


def optimal_edit_paths(G1, G2, node_match=None, edge_match=None,
                       node_subst_cost=None, node_del_cost=None,
                       node_ins_cost=None,
                       edge_subst_cost=None, edge_del_cost=None,
                       edge_ins_cost=None,
                       upper_bound=None):
    """Returns all minimum-cost edit paths transforming G1 to G2.

    Graph edit path is a sequence of node and edge edit operations
    transforming graph G1 to graph isomorphic to G2.  Edit operations
    include substitutions, deletions, and insertions.

    Parameters
    ----------
    G1, G2: graphs
        The two graphs G1 and G2 must be of the same type.

    node_match : callable
        A function that returns True if node n1 in G1 and n2 in G2
        should be considered equal during matching.

        The function will be called like

           node_match(G1.nodes[n1], G2.nodes[n2]).

        That is, the function will receive the node attribute
        dictionaries for n1 and n2 as inputs.

        Ignored if node_subst_cost is specified.  If neither
        node_match nor node_subst_cost are specified then node
        attributes are not considered.

    edge_match : callable
        A function that returns True if the edge attribute dictionaries
        for the pair of nodes (u1, v1) in G1 and (u2, v2) in G2 should
        be considered equal during matching.

        The function will be called like

           edge_match(G1[u1][v1], G2[u2][v2]).

        That is, the function will receive the edge attribute
        dictionaries of the edges under consideration.

        Ignored if edge_subst_cost is specified.  If neither
        edge_match nor edge_subst_cost are specified then edge
        attributes are not considered.

    node_subst_cost, node_del_cost, node_ins_cost : callable
        Functions that return the costs of node substitution, node
        deletion, and node insertion, respectively.

        The functions will be called like

           node_subst_cost(G1.nodes[n1], G2.nodes[n2]),
           node_del_cost(G1.nodes[n1]),
           node_ins_cost(G2.nodes[n2]).

        That is, the functions will receive the node attribute
        dictionaries as inputs.  The functions are expected to return
        positive numeric values.

        Function node_subst_cost overrides node_match if specified.
        If neither node_match nor node_subst_cost are specified then
        default node substitution cost of 0 is used (node attributes
        are not considered during matching).

        If node_del_cost is not specified then default node deletion
        cost of 1 is used.  If node_ins_cost is not specified then
        default node insertion cost of 1 is used.

    edge_subst_cost, edge_del_cost, edge_ins_cost : callable
        Functions that return the costs of edge substitution, edge
        deletion, and edge insertion, respectively.

        The functions will be called like

           edge_subst_cost(G1[u1][v1], G2[u2][v2]),
           edge_del_cost(G1[u1][v1]),
           edge_ins_cost(G2[u2][v2]).

        That is, the functions will receive the edge attribute
        dictionaries as inputs.  The functions are expected to return
        positive numeric values.

        Function edge_subst_cost overrides edge_match if specified.
        If neither edge_match nor edge_subst_cost are specified then
        default edge substitution cost of 0 is used (edge attributes
        are not considered during matching).

        If edge_del_cost is not specified then default edge deletion
        cost of 1 is used.  If edge_ins_cost is not specified then
        default edge insertion cost of 1 is used.

    upper_bound : numeric
        Maximum edit distance to consider.

    Returns
    -------
    edit_paths : list of tuples (node_edit_path, edge_edit_path)
        node_edit_path : list of tuples (u, v)
        edge_edit_path : list of tuples ((u1, v1), (u2, v2))

    cost : numeric
        Optimal edit path cost (graph edit distance).

    Examples
    --------
    >>> G1 = nx.cycle_graph(6)
    >>> G2 = nx.wheel_graph(7)
    >>> paths, cost = nx.optimal_edit_paths(G1, G2)
    >>> len(paths)
    84
    >>> cost
    7.0

    See Also
    --------
    graph_edit_distance, optimize_edit_paths

    References
    ----------
    .. [1] Zeina Abu-Aisheh, Romain Raveaux, Jean-Yves Ramel, Patrick
       Martineau. An Exact Graph Edit Distance Algorithm for Solving
       Pattern Recognition Problems. 4th International Conference on
       Pattern Recognition Applications and Methods 2015, Jan 2015,
       Lisbon, Portugal. 2015,
       <10.5220/0005209202710278>. <hal-01168816>
       https://hal.archives-ouvertes.fr/hal-01168816

    """
    paths = list()
    bestcost = None
    for vertex_path, edge_path, cost in \
        optimize_edit_paths(G1, G2, node_match, edge_match,
                            node_subst_cost, node_del_cost, node_ins_cost,
                            edge_subst_cost, edge_del_cost, edge_ins_cost,
                            upper_bound, False):
        #assert bestcost is None or cost <= bestcost
        if bestcost is not None and cost < bestcost:
            paths = list()
        paths.append((vertex_path, edge_path))
        bestcost = cost
    return paths, bestcost


def optimize_graph_edit_distance(G1, G2, node_match=None, edge_match=None,
                                 node_subst_cost=None, node_del_cost=None,
                                 node_ins_cost=None,
                                 edge_subst_cost=None, edge_del_cost=None,
                                 edge_ins_cost=None,
                                 upper_bound=None):
    """Returns consecutive approximations of GED (graph edit distance)
    between graphs G1 and G2.

    Graph edit distance is a graph similarity measure analogous to
    Levenshtein distance for strings.  It is defined as minimum cost
    of edit path (sequence of node and edge edit operations)
    transforming graph G1 to graph isomorphic to G2.

    Parameters
    ----------
    G1, G2: graphs
        The two graphs G1 and G2 must be of the same type.

    node_match : callable
        A function that returns True if node n1 in G1 and n2 in G2
        should be considered equal during matching.

        The function will be called like

           node_match(G1.nodes[n1], G2.nodes[n2]).

        That is, the function will receive the node attribute
        dictionaries for n1 and n2 as inputs.

        Ignored if node_subst_cost is specified.  If neither
        node_match nor node_subst_cost are specified then node
        attributes are not considered.

    edge_match : callable
        A function that returns True if the edge attribute dictionaries
        for the pair of nodes (u1, v1) in G1 and (u2, v2) in G2 should
        be considered equal during matching.

        The function will be called like

           edge_match(G1[u1][v1], G2[u2][v2]).

        That is, the function will receive the edge attribute
        dictionaries of the edges under consideration.

        Ignored if edge_subst_cost is specified.  If neither
        edge_match nor edge_subst_cost are specified then edge
        attributes are not considered.

    node_subst_cost, node_del_cost, node_ins_cost : callable
        Functions that return the costs of node substitution, node
        deletion, and node insertion, respectively.

        The functions will be called like

           node_subst_cost(G1.nodes[n1], G2.nodes[n2]),
           node_del_cost(G1.nodes[n1]),
           node_ins_cost(G2.nodes[n2]).

        That is, the functions will receive the node attribute
        dictionaries as inputs.  The functions are expected to return
        positive numeric values.

        Function node_subst_cost overrides node_match if specified.
        If neither node_match nor node_subst_cost are specified then
        default node substitution cost of 0 is used (node attributes
        are not considered during matching).

        If node_del_cost is not specified then default node deletion
        cost of 1 is used.  If node_ins_cost is not specified then
        default node insertion cost of 1 is used.

    edge_subst_cost, edge_del_cost, edge_ins_cost : callable
        Functions that return the costs of edge substitution, edge
        deletion, and edge insertion, respectively.

        The functions will be called like

           edge_subst_cost(G1[u1][v1], G2[u2][v2]),
           edge_del_cost(G1[u1][v1]),
           edge_ins_cost(G2[u2][v2]).

        That is, the functions will receive the edge attribute
        dictionaries as inputs.  The functions are expected to return
        positive numeric values.

        Function edge_subst_cost overrides edge_match if specified.
        If neither edge_match nor edge_subst_cost are specified then
        default edge substitution cost of 0 is used (edge attributes
        are not considered during matching).

        If edge_del_cost is not specified then default edge deletion
        cost of 1 is used.  If edge_ins_cost is not specified then
        default edge insertion cost of 1 is used.

    upper_bound : numeric
        Maximum edit distance to consider.

    Returns
    -------
    Generator of consecutive approximations of graph edit distance.

    Examples
    --------
    >>> G1 = nx.cycle_graph(6)
    >>> G2 = nx.wheel_graph(7)
    >>> for v in nx.optimize_graph_edit_distance(G1, G2):
    ...     minv = v
    >>> minv
    7.0

    See Also
    --------
    graph_edit_distance, optimize_edit_paths

    References
    ----------
    .. [1] Zeina Abu-Aisheh, Romain Raveaux, Jean-Yves Ramel, Patrick
       Martineau. An Exact Graph Edit Distance Algorithm for Solving
       Pattern Recognition Problems. 4th International Conference on
       Pattern Recognition Applications and Methods 2015, Jan 2015,
       Lisbon, Portugal. 2015,
       <10.5220/0005209202710278>. <hal-01168816>
       https://hal.archives-ouvertes.fr/hal-01168816
    """
    for vertex_path, edge_path, cost in \
        optimize_edit_paths(G1, G2, node_match, edge_match,
                            node_subst_cost, node_del_cost, node_ins_cost,
                            edge_subst_cost, edge_del_cost, edge_ins_cost,
                            upper_bound, True):
        yield cost


def optimize_edit_paths(G1, G2, node_match=None, edge_match=None,
                        node_subst_cost=None, node_del_cost=None,
                        node_ins_cost=None,
                        edge_subst_cost=None, edge_del_cost=None,
                        edge_ins_cost=None,
                        upper_bound=None, strictly_decreasing=True):
    """GED (graph edit distance) calculation: advanced interface.

    Graph edit path is a sequence of node and edge edit operations
    transforming graph G1 to graph isomorphic to G2.  Edit operations
    include substitutions, deletions, and insertions.

    Graph edit distance is defined as minimum cost of edit path.

    Parameters
    ----------
    G1, G2: graphs
        The two graphs G1 and G2 must be of the same type.

    node_match : callable
        A function that returns True if node n1 in G1 and n2 in G2
        should be considered equal during matching.

        The function will be called like

           node_match(G1.nodes[n1], G2.nodes[n2]).

        That is, the function will receive the node attribute
        dictionaries for n1 and n2 as inputs.

        Ignored if node_subst_cost is specified.  If neither
        node_match nor node_subst_cost are specified then node
        attributes are not considered.

    edge_match : callable
        A function that returns True if the edge attribute dictionaries
        for the pair of nodes (u1, v1) in G1 and (u2, v2) in G2 should
        be considered equal during matching.

        The function will be called like

           edge_match(G1[u1][v1], G2[u2][v2]).

        That is, the function will receive the edge attribute
        dictionaries of the edges under consideration.

        Ignored if edge_subst_cost is specified.  If neither
        edge_match nor edge_subst_cost are specified then edge
        attributes are not considered.

    node_subst_cost, node_del_cost, node_ins_cost : callable
        Functions that return the costs of node substitution, node
        deletion, and node insertion, respectively.

        The functions will be called like

           node_subst_cost(G1.nodes[n1], G2.nodes[n2]),
           node_del_cost(G1.nodes[n1]),
           node_ins_cost(G2.nodes[n2]).

        That is, the functions will receive the node attribute
        dictionaries as inputs.  The functions are expected to return
        positive numeric values.

        Function node_subst_cost overrides node_match if specified.
        If neither node_match nor node_subst_cost are specified then
        default node substitution cost of 0 is used (node attributes
        are not considered during matching).

        If node_del_cost is not specified then default node deletion
        cost of 1 is used.  If node_ins_cost is not specified then
        default node insertion cost of 1 is used.

    edge_subst_cost, edge_del_cost, edge_ins_cost : callable
        Functions that return the costs of edge substitution, edge
        deletion, and edge insertion, respectively.

        The functions will be called like

           edge_subst_cost(G1[u1][v1], G2[u2][v2]),
           edge_del_cost(G1[u1][v1]),
           edge_ins_cost(G2[u2][v2]).

        That is, the functions will receive the edge attribute
        dictionaries as inputs.  The functions are expected to return
        positive numeric values.

        Function edge_subst_cost overrides edge_match if specified.
        If neither edge_match nor edge_subst_cost are specified then
        default edge substitution cost of 0 is used (edge attributes
        are not considered during matching).

        If edge_del_cost is not specified then default edge deletion
        cost of 1 is used.  If edge_ins_cost is not specified then
        default edge insertion cost of 1 is used.

    upper_bound : numeric
        Maximum edit distance to consider.

    strictly_decreasing : bool
        If True, return consecutive approximations of strictly
        decreasing cost.  Otherwise, return all edit paths of cost
        less than or equal to the previous minimum cost.

    Returns
    -------
    Generator of tuples (node_edit_path, edge_edit_path, cost)
        node_edit_path : list of tuples (u, v)
        edge_edit_path : list of tuples ((u1, v1), (u2, v2))
        cost : numeric

    See Also
    --------
    graph_edit_distance, optimize_graph_edit_distance, optimal_edit_paths

    References
    ----------
    .. [1] Zeina Abu-Aisheh, Romain Raveaux, Jean-Yves Ramel, Patrick
       Martineau. An Exact Graph Edit Distance Algorithm for Solving
       Pattern Recognition Problems. 4th International Conference on
       Pattern Recognition Applications and Methods 2015, Jan 2015,
       Lisbon, Portugal. 2015,
       <10.5220/0005209202710278>. <hal-01168816>
       https://hal.archives-ouvertes.fr/hal-01168816

    """
    # TODO: support DiGraph

    import numpy as np
    from scipy.optimize import linear_sum_assignment

    class CostMatrix:
        def __init__(self, C, lsa_row_ind, lsa_col_ind, ls):
            #assert C.shape[0] == len(lsa_row_ind)
            #assert C.shape[1] == len(lsa_col_ind)
            #assert len(lsa_row_ind) == len(lsa_col_ind)
            #assert set(lsa_row_ind) == set(range(len(lsa_row_ind)))
            #assert set(lsa_col_ind) == set(range(len(lsa_col_ind)))
            #assert ls == C[lsa_row_ind, lsa_col_ind].sum()
            self.C = C
            self.lsa_row_ind = lsa_row_ind
            self.lsa_col_ind = lsa_col_ind
            self.ls = ls

    def make_CostMatrix(C, m, n):
        #assert(C.shape == (m + n, m + n))
        lsa_row_ind, lsa_col_ind = linear_sum_assignment(C)

        # Fixup dummy assignments:
        # each substitution i<->j should have dummy assignment m+j<->n+i
        # NOTE: fast reduce of Cv relies on it
        #assert len(lsa_row_ind) == len(lsa_col_ind)
        indexes = zip(range(len(lsa_row_ind)), lsa_row_ind, lsa_col_ind)
        subst_ind = list(k for k, i, j in indexes if i < m and j < n)
        indexes = zip(range(len(lsa_row_ind)), lsa_row_ind, lsa_col_ind)
        dummy_ind = list(k for k, i, j in indexes if i >= m and j >= n)
        #assert len(subst_ind) == len(dummy_ind)
        lsa_row_ind[dummy_ind] = lsa_col_ind[subst_ind] + m
        lsa_col_ind[dummy_ind] = lsa_row_ind[subst_ind] + n

        return CostMatrix(C, lsa_row_ind, lsa_col_ind,
                          C[lsa_row_ind, lsa_col_ind].sum())

    def extract_C(C, i, j, m, n):
        #assert(C.shape == (m + n, m + n))
        row_ind = [k in i or k - m in j for k in range(m + n)]
        col_ind = [k in j or k - n in i for k in range(m + n)]
        return C[row_ind, :][:, col_ind]

    def reduce_C(C, i, j, m, n):
        #assert(C.shape == (m + n, m + n))
        row_ind = [k not in i and k - m not in j for k in range(m + n)]
        col_ind = [k not in j and k - n not in i for k in range(m + n)]
        return C[row_ind, :][:, col_ind]

    def reduce_ind(ind, i):
        #assert set(ind) == set(range(len(ind)))
        rind = ind[[k not in i for k in ind]]
        for k in set(i):
            rind[rind >= k] -= 1
        return rind

    def match_edges(u, v, pending_g, pending_h, Ce, matched_uv=[]):
        """
        Parameters:
            u, v: matched vertices, u=None or v=None for
               deletion/insertion
            pending_g, pending_h: lists of edges not yet mapped
            Ce: CostMatrix of pending edge mappings
            matched_uv: partial vertex edit path
                list of tuples (u, v) of previously matched vertex
                    mappings u<->v, u=None or v=None for
                    deletion/insertion

        Returns:
            list of (i, j): indices of edge mappings g<->h
            localCe: local CostMatrix of edge mappings
                (basically submatrix of Ce at cross of rows i, cols j)
        """
        M = len(pending_g)
        N = len(pending_h)
        #assert Ce.C.shape == (M + N, M + N)

        g_ind = [i for i in range(M) if pending_g[i][:2] == (u, u) or
                 any(pending_g[i][:2] in ((p, u), (u, p))
                     for p, q in matched_uv)]
        h_ind = [j for j in range(N) if pending_h[j][:2] == (v, v) or
                 any(pending_h[j][:2] in ((q, v), (v, q))
                     for p, q in matched_uv)]
        m = len(g_ind)
        n = len(h_ind)

        if m or n:
            C = extract_C(Ce.C, g_ind, h_ind, M, N)
            #assert C.shape == (m + n, m + n)

            # Forbid structurally invalid matches
            # NOTE: inf remembered from Ce construction
            for k, i in zip(range(m), g_ind):
                g = pending_g[i][:2]
                for l, j in zip(range(n), h_ind):
                    h = pending_h[j][:2]
                    if nx.is_directed(G1) or nx.is_directed(G2):
                        if any(g == (p, u) and h == (q, v) or
                               g == (u, p) and h == (v, q)
                               for p, q in matched_uv):
                            continue
                    else:
                        if any(g in ((p, u), (u, p)) and h in ((q, v), (v, q))
                               for p, q in matched_uv):
                            continue
                    if g == (u, u):
                        continue
                    if h == (v, v):
                        continue
                    C[k, l] = inf

            localCe = make_CostMatrix(C, m, n)
            ij = list((g_ind[k] if k < m else M + h_ind[l],
                       h_ind[l] if l < n else N + g_ind[k])
                      for k, l in zip(localCe.lsa_row_ind, localCe.lsa_col_ind)
                      if k < m or l < n)

        else:
            ij = []
            localCe = CostMatrix(np.empty((0, 0)), [], [], 0)

        return ij, localCe

    def reduce_Ce(Ce, ij, m, n):
        if len(ij):
            i, j = zip(*ij)
            m_i = m - sum(1 for t in i if t < m)
            n_j = n - sum(1 for t in j if t < n)
            return make_CostMatrix(reduce_C(Ce.C, i, j, m, n), m_i, n_j)
        else:
            return Ce

    def get_edit_ops(matched_uv, pending_u, pending_v, Cv,
                     pending_g, pending_h, Ce, matched_cost):
        """
        Parameters:
            matched_uv: partial vertex edit path
                list of tuples (u, v) of vertex mappings u<->v,
                u=None or v=None for deletion/insertion
            pending_u, pending_v: lists of vertices not yet mapped
            Cv: CostMatrix of pending vertex mappings
            pending_g, pending_h: lists of edges not yet mapped
            Ce: CostMatrix of pending edge mappings
            matched_cost: cost of partial edit path

        Returns:
            sequence of
                (i, j): indices of vertex mapping u<->v
                Cv_ij: reduced CostMatrix of pending vertex mappings
                    (basically Cv with row i, col j removed)
                list of (x, y): indices of edge mappings g<->h
                Ce_xy: reduced CostMatrix of pending edge mappings
                    (basically Ce with rows x, cols y removed)
                cost: total cost of edit operation
            NOTE: most promising ops first
        """
        m = len(pending_u)
        n = len(pending_v)
        #assert Cv.C.shape == (m + n, m + n)

        # 1) a vertex mapping from optimal linear sum assignment
        i, j = min((k, l) for k, l in zip(Cv.lsa_row_ind, Cv.lsa_col_ind)
                   if k < m or l < n)
        xy, localCe = match_edges(pending_u[i] if i < m else None,
                                  pending_v[j] if j < n else None,
                                  pending_g, pending_h, Ce, matched_uv)
        Ce_xy = reduce_Ce(Ce, xy, len(pending_g), len(pending_h))
        #assert Ce.ls <= localCe.ls + Ce_xy.ls
        if prune(matched_cost + Cv.ls + localCe.ls + Ce_xy.ls):
            pass
        else:
            # get reduced Cv efficiently
            Cv_ij = CostMatrix(reduce_C(Cv.C, (i,), (j,), m, n),
                               reduce_ind(Cv.lsa_row_ind, (i, m + j)),
                               reduce_ind(Cv.lsa_col_ind, (j, n + i)),
                               Cv.ls - Cv.C[i, j])
            yield (i, j), Cv_ij, xy, Ce_xy, Cv.C[i, j] + localCe.ls

        # 2) other candidates, sorted by lower-bound cost estimate
        other = list()
        fixed_i, fixed_j = i, j
        if m <= n:
            candidates = ((t, fixed_j) for t in range(m + n)
                          if t != fixed_i and (t < m or t == m + fixed_j))
        else:
            candidates = ((fixed_i, t) for t in range(m + n)
                          if t != fixed_j and (t < n or t == n + fixed_i))
        for i, j in candidates:
            if prune(matched_cost + Cv.C[i, j] + Ce.ls):
                continue
            Cv_ij = make_CostMatrix(reduce_C(Cv.C, (i,), (j,), m, n),
                                    m - 1 if i < m else m,
                                    n - 1 if j < n else n)
            #assert Cv.ls <= Cv.C[i, j] + Cv_ij.ls
            if prune(matched_cost + Cv.C[i, j] + Cv_ij.ls + Ce.ls):
                continue
            xy, localCe = match_edges(pending_u[i] if i < m else None,
                                      pending_v[j] if j < n else None,
                                      pending_g, pending_h, Ce, matched_uv)
            if prune(matched_cost + Cv.C[i, j] + Cv_ij.ls + localCe.ls):
                continue
            Ce_xy = reduce_Ce(Ce, xy, len(pending_g), len(pending_h))
            #assert Ce.ls <= localCe.ls + Ce_xy.ls
            if prune(matched_cost + Cv.C[i, j] + Cv_ij.ls + localCe.ls +
                     Ce_xy.ls):
                continue
            other.append(((i, j), Cv_ij, xy, Ce_xy, Cv.C[i, j] + localCe.ls))

        yield from sorted(other, key=lambda t: t[4] + t[1].ls + t[3].ls)

    def get_edit_paths(matched_uv, pending_u, pending_v, Cv,
                       matched_gh, pending_g, pending_h, Ce, matched_cost):
        """
        Parameters:
            matched_uv: partial vertex edit path
                list of tuples (u, v) of vertex mappings u<->v,
                u=None or v=None for deletion/insertion
            pending_u, pending_v: lists of vertices not yet mapped
            Cv: CostMatrix of pending vertex mappings
            matched_gh: partial edge edit path
                list of tuples (g, h) of edge mappings g<->h,
                g=None or h=None for deletion/insertion
            pending_g, pending_h: lists of edges not yet mapped
            Ce: CostMatrix of pending edge mappings
            matched_cost: cost of partial edit path

        Returns:
            sequence of (vertex_path, edge_path, cost)
                vertex_path: complete vertex edit path
                    list of tuples (u, v) of vertex mappings u<->v,
                    u=None or v=None for deletion/insertion
                edge_path: complete edge edit path
                    list of tuples (g, h) of edge mappings g<->h,
                    g=None or h=None for deletion/insertion
                cost: total cost of edit path
            NOTE: path costs are non-increasing
        """
        #debug_print('matched-uv:', matched_uv)
        #debug_print('matched-gh:', matched_gh)
        #debug_print('matched-cost:', matched_cost)
        #debug_print('pending-u:', pending_u)
        #debug_print('pending-v:', pending_v)
        # debug_print(Cv.C)
        #assert list(sorted(G1.nodes)) == list(sorted(list(u for u, v in matched_uv if u is not None) + pending_u))
        #assert list(sorted(G2.nodes)) == list(sorted(list(v for u, v in matched_uv if v is not None) + pending_v))
        #debug_print('pending-g:', pending_g)
        #debug_print('pending-h:', pending_h)
        # debug_print(Ce.C)
        #assert list(sorted(G1.edges)) == list(sorted(list(g for g, h in matched_gh if g is not None) + pending_g))
        #assert list(sorted(G2.edges)) == list(sorted(list(h for g, h in matched_gh if h is not None) + pending_h))
        # debug_print()

        if prune(matched_cost + Cv.ls + Ce.ls):
            return

        if not max(len(pending_u), len(pending_v)):
            #assert not len(pending_g)
            #assert not len(pending_h)
            # path completed!
            #assert matched_cost <= maxcost.value
            maxcost.value = min(maxcost.value, matched_cost)
            yield matched_uv, matched_gh, matched_cost

        else:
            edit_ops = get_edit_ops(matched_uv, pending_u, pending_v, Cv,
                                    pending_g, pending_h, Ce, matched_cost)
            for ij, Cv_ij, xy, Ce_xy, edit_cost in edit_ops:
                i, j = ij
                #assert Cv.C[i, j] + sum(Ce.C[t] for t in xy) == edit_cost
                if prune(matched_cost + edit_cost + Cv_ij.ls + Ce_xy.ls):
                    continue

                # dive deeper
                u = pending_u.pop(i) if i < len(pending_u) else None
                v = pending_v.pop(j) if j < len(pending_v) else None
                matched_uv.append((u, v))
                for x, y in xy:
                    len_g = len(pending_g)
                    len_h = len(pending_h)
                    matched_gh.append((pending_g[x] if x < len_g else None,
                                       pending_h[y] if y < len_h else None))
                sortedx = list(sorted(x for x, y in xy))
                sortedy = list(sorted(y for x, y in xy))
                G = list((pending_g.pop(x) if x < len(pending_g) else None)
                         for x in reversed(sortedx))
                H = list((pending_h.pop(y) if y < len(pending_h) else None)
                         for y in reversed(sortedy))

                yield from get_edit_paths(matched_uv, pending_u, pending_v,
                                          Cv_ij,
                                          matched_gh, pending_g, pending_h,
                                          Ce_xy,
                                          matched_cost + edit_cost)

                # backtrack
                if u is not None:
                    pending_u.insert(i, u)
                if v is not None:
                    pending_v.insert(j, v)
                matched_uv.pop()
                for x, g in zip(sortedx, reversed(G)):
                    if g is not None:
                        pending_g.insert(x, g)
                for y, h in zip(sortedy, reversed(H)):
                    if h is not None:
                        pending_h.insert(y, h)
                for t in xy:
                    matched_gh.pop()

    # Initialization

    pending_u = list(G1.nodes)
    pending_v = list(G2.nodes)

    # cost matrix of vertex mappings
    m = len(pending_u)
    n = len(pending_v)
    C = np.zeros((m + n, m + n))
    if node_subst_cost:
        C[0:m, 0:n] = np.array([node_subst_cost(G1.nodes[u], G2.nodes[v])
                                for u in pending_u for v in pending_v]
                               ).reshape(m, n)
    elif node_match:
        C[0:m, 0:n] = np.array([1 - int(node_match(G1.nodes[u], G2.nodes[v]))
                                for u in pending_u for v in pending_v]
                               ).reshape(m, n)
    else:
        # all zeroes
        pass
    #assert not min(m, n) or C[0:m, 0:n].min() >= 0
    if node_del_cost:
        del_costs = [node_del_cost(G1.nodes[u]) for u in pending_u]
    else:
        del_costs = [1] * len(pending_u)
    #assert not m or min(del_costs) >= 0
    if node_ins_cost:
        ins_costs = [node_ins_cost(G2.nodes[v]) for v in pending_v]
    else:
        ins_costs = [1] * len(pending_v)
    #assert not n or min(ins_costs) >= 0
    inf = C[0:m, 0:n].sum() + sum(del_costs) + sum(ins_costs) + 1
    C[0:m, n:n + m] = np.array([del_costs[i] if i == j else inf
                                for i in range(m) for j in range(m)]
                               ).reshape(m, m)
    C[m:m + n, 0:n] = np.array([ins_costs[i] if i == j else inf
                                for i in range(n) for j in range(n)]
                               ).reshape(n, n)
    Cv = make_CostMatrix(C, m, n)
    #debug_print('Cv: {} x {}'.format(m, n))
    # debug_print(Cv.C)

    pending_g = list(G1.edges)
    pending_h = list(G2.edges)

    # cost matrix of edge mappings
    m = len(pending_g)
    n = len(pending_h)
    C = np.zeros((m + n, m + n))
    if edge_subst_cost:
        C[0:m, 0:n] = np.array([edge_subst_cost(G1.edges[g], G2.edges[h])
                                for g in pending_g for h in pending_h]
                               ).reshape(m, n)
    elif edge_match:
        C[0:m, 0:n] = np.array([1 - int(edge_match(G1.edges[g], G2.edges[h]))
                                for g in pending_g for h in pending_h]
                               ).reshape(m, n)
    else:
        # all zeroes
        pass
    #assert not min(m, n) or C[0:m, 0:n].min() >= 0
    if edge_del_cost:
        del_costs = [edge_del_cost(G1.edges[g]) for g in pending_g]
    else:
        del_costs = [1] * len(pending_g)
    #assert not m or min(del_costs) >= 0
    if edge_ins_cost:
        ins_costs = [edge_ins_cost(G2.edges[h]) for h in pending_h]
    else:
        ins_costs = [1] * len(pending_h)
    #assert not n or min(ins_costs) >= 0
    inf = C[0:m, 0:n].sum() + sum(del_costs) + sum(ins_costs) + 1
    C[0:m, n:n + m] = np.array([del_costs[i] if i == j else inf
                                for i in range(m) for j in range(m)]
                               ).reshape(m, m)
    C[m:m + n, 0:n] = np.array([ins_costs[i] if i == j else inf
                                for i in range(n) for j in range(n)]
                               ).reshape(n, n)
    Ce = make_CostMatrix(C, m, n)
    #debug_print('Ce: {} x {}'.format(m, n))
    # debug_print(Ce.C)
    # debug_print()

    class MaxCost:
        def __init__(self):
            # initial upper-bound estimate
            # NOTE: should work for empty graph
            self.value = Cv.C.sum() + Ce.C.sum() + 1
    maxcost = MaxCost()

    def prune(cost):
        if upper_bound is not None:
            if cost > upper_bound:
                return True
        if cost > maxcost.value:
            return True
        elif strictly_decreasing and cost >= maxcost.value:
            return True

    # Now go!

    for vertex_path, edge_path, cost in \
        get_edit_paths([], pending_u, pending_v, Cv,
                       [], pending_g, pending_h, Ce, 0):
        #assert sorted(G1.nodes) == sorted(u for u, v in vertex_path if u is not None)
        #assert sorted(G2.nodes) == sorted(v for u, v in vertex_path if v is not None)
        #assert sorted(G1.edges) == sorted(g for g, h in edge_path if g is not None)
        #assert sorted(G2.edges) == sorted(h for g, h in edge_path if h is not None)
        #print(vertex_path, edge_path, cost, file = sys.stderr)
        #assert cost == maxcost.value
        yield list(vertex_path), list(edge_path), cost


def _is_close(d1, d2, atolerance=0, rtolerance=0):
    """Determines whether two adjacency matrices are within
    a provided tolerance.
    
    Parameters
    ----------
    d1 : dict
        Adjacency dictionary
    
    d2 : dict
        Adjacency dictionary
    
    atolerance : float
        Some scalar tolerance value to determine closeness
    
    rtolerance : float
        A scalar tolerance value that will be some proportion
        of ``d2``'s value
    
    Returns
    -------
    closeness : bool
        If all of the nodes within ``d1`` and ``d2`` are within
        a predefined tolerance, they are considered "close" and
        this method will return True. Otherwise, this method will
        return False.
    
    """
    # Pre-condition: d1 and d2 have the same keys at each level if they
    # are dictionaries.
    if not isinstance(d1, dict) and not isinstance(d2, dict):
        return abs(d1 - d2) <= atolerance + rtolerance * abs(d2)
    return all(all(_is_close(d1[u][v], d2[u][v]) for v in d1[u]) for u in d1)


def simrank_similarity(G, source=None, target=None, importance_factor=0.9,
                       max_iterations=100, tolerance=1e-4):
    """Returns the SimRank similarity of nodes in the graph ``G``.

    SimRank is a similarity metric that says "two objects are considered
    to be similar if they are referenced by similar objects." [1]_.
    
    The pseudo-code definition from the paper is::

        def simrank(G, u, v):
            in_neighbors_u = G.predecessors(u)
            in_neighbors_v = G.predecessors(v)
            scale = C / (len(in_neighbors_u) * len(in_neighbors_v))
            return scale * sum(simrank(G, w, x)
                               for w, x in product(in_neighbors_u,
                                                   in_neighbors_v))
    
    where ``G`` is the graph, ``u`` is the source, ``v`` is the target,
    and ``C`` is a float decay or importance factor between 0 and 1.
    
    The SimRank algorithm for determining node similarity is defined in
    [2]_.

    Parameters
    ----------
    G : NetworkX graph
        A NetworkX graph

    source : node
        If this is specified, the returned dictionary maps each node
        ``v`` in the graph to the similarity between ``source`` and
        ``v``.

    target : node
        If both ``source`` and ``target`` are specified, the similarity
        value between ``source`` and ``target`` is returned. If
        ``target`` is specified but ``source`` is not, this argument is
        ignored.

    importance_factor : float
        The relative importance of indirect neighbors with respect to
        direct neighbors.

    max_iterations : integer
        Maximum number of iterations.

    tolerance : float
        Error tolerance used to check convergence. When an iteration of
        the algorithm finds that no similarity value changes more than
        this amount, the algorithm halts.

    Returns
    -------
    similarity : dictionary or float
        If ``source`` and ``target`` are both ``None``, this returns a
        dictionary of dictionaries, where keys are node pairs and value
        are similarity of the pair of nodes.

        If ``source`` is not ``None`` but ``target`` is, this returns a
        dictionary mapping node to the similarity of ``source`` and that
        node.

        If neither ``source`` nor ``target`` is ``None``, this returns
        the similarity value for the given pair of nodes.

    Examples
    --------
    If the nodes of the graph are numbered from zero to *n - 1*, where *n*
    is the number of nodes in the graph, you can create a SimRank matrix
    from the return value of this function where the node numbers are
    the row and column indices of the matrix::

        >>> import networkx as nx
        >>> from numpy import array
        >>> G = nx.cycle_graph(4)
        >>> sim = nx.simrank_similarity(G)
        >>> lol = [[sim[u][v] for v in sorted(sim[u])] for u in sorted(sim)]
        >>> sim_array = array(lol)

    References
    ----------
    .. [1] https://en.wikipedia.org/wiki/SimRank
    .. [2] G. Jeh and J. Widom.
           "SimRank: a measure of structural-context similarity",
           In KDD'02: Proceedings of the Eighth ACM SIGKDD
           International Conference on Knowledge Discovery and Data Mining,
           pp. 538--543. ACM Press, 2002.
    """
    prevsim = None

    # build up our similarity adjacency dictionary output
    newsim = {u: {v: 1 if u == v else 0 for v in G} for u in G}

    # These functions compute the update to the similarity value of the nodes
    # `u` and `v` with respect to the previous similarity values.
    avg_sim = lambda s: sum(newsim[w][x] for (w, x) in s) / len(s) if s else 0.0
    sim = lambda u, v: importance_factor * avg_sim(list(product(G[u], G[v])))

    for _ in range(max_iterations):
        if prevsim and _is_close(prevsim, newsim, tolerance):
            break
        prevsim = newsim
        newsim = {u: {v: sim(u, v) if u is not v else 1
                      for v in newsim[u]} for u in newsim}

    if source is not None and target is not None:
        return newsim[source][target]
    if source is not None:
        return newsim[source]
    return newsim


def simrank_similarity_numpy(G, source=None, target=None, importance_factor=0.9,
                             max_iterations=100, tolerance=1e-4):
    """Calculate SimRank of nodes in ``G`` using matrices with ``numpy``.

    The SimRank algorithm for determining node similarity is defined in
    [1]_.

    Parameters
    ----------
    G : NetworkX graph
        A NetworkX graph

    source : node
        If this is specified, the returned dictionary maps each node
        ``v`` in the graph to the similarity between ``source`` and
        ``v``.

    target : node
        If both ``source`` and ``target`` are specified, the similarity
        value between ``source`` and ``target`` is returned. If
        ``target`` is specified but ``source`` is not, this argument is
        ignored.

    importance_factor : float
        The relative importance of indirect neighbors with respect to
        direct neighbors.

    max_iterations : integer
        Maximum number of iterations.

    tolerance : float
        Error tolerance used to check convergence. When an iteration of
        the algorithm finds that no similarity value changes more than
        this amount, the algorithm halts.

    Returns
    -------
    similarity : dictionary or float
        If ``source`` and ``target`` are both ``None``, this returns a
        dictionary of dictionaries, where keys are node pairs and value
        are similarity of the pair of nodes.

        If ``source`` is not ``None`` but ``target`` is, this returns a
        dictionary mapping node to the similarity of ``source`` and that
        node.

        If neither ``source`` nor ``target`` is ``None``, this returns
        the similarity value for the given pair of nodes.

    Examples
    --------
        >>> import networkx as nx
        >>> from numpy import array
        >>> G = nx.cycle_graph(4)
        >>> sim = nx.simrank_similarity_numpy(G)

    References
    ----------
    .. [1] G. Jeh and J. Widom.
           "SimRank: a measure of structural-context similarity",
           In KDD'02: Proceedings of the Eighth ACM SIGKDD
           International Conference on Knowledge Discovery and Data Mining,
           pp. 538--543. ACM Press, 2002.
    """
    # This algorithm follows roughly
    #
    #     S = max{C * (A.T * S * A), I}
    #
    # where C is the importance factor, A is the column normalized
    # adjacency matrix, and I is the identity matrix.
    import numpy as np
    adjacency_matrix = nx.to_numpy_array(G)

    # column-normalize the ``adjacency_matrix``
    adjacency_matrix /= adjacency_matrix.sum(axis=0)

    newsim = np.eye(adjacency_matrix.shape[0], dtype=np.float64)
    for _ in range(max_iterations):
        prevsim = np.copy(newsim)
        newsim = importance_factor * np.matmul(
            np.matmul(adjacency_matrix.T, prevsim), adjacency_matrix)
        np.fill_diagonal(newsim, 1.0)

        if np.allclose(prevsim, newsim, atol=tolerance):
            break

    if source is not None and target is not None:
        return newsim[source, target]
    if source is not None:
        return newsim[source]
    return newsim


# fixture for pytest
def setup_module(module):
    import pytest
    numpy = pytest.importorskip('numpy')
    scipy = pytest.importorskip('scipy')

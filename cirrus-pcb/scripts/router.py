"""Small grid maze router for adding a few tracks to an existing KiCad board.
Obstacles honor the board's clearance rules; DRC is the final judge."""
import heapq, math
import numpy as np
import pcbnew

MM = 1e6  # nm per mm

class Router:
    def __init__(self, board, x0, y0, x1, y1, res=0.05, clearance=0.2, width=0.25,
                 hole_clear=0.25, edge_clear=0.3, via_d=0.8):
        self.b, self.res = board, res
        self.x0, self.y0 = x0, y0
        self.nx = int(round((x1 - x0) / res)) + 1
        self.ny = int(round((y1 - y0) / res)) + 1
        xs = x0 + np.arange(self.nx) * res
        ys = y0 + np.arange(self.ny) * res
        self.X, self.Y = np.meshgrid(xs, ys)          # shape (ny, nx)
        self.cl, self.w, self.hc, self.ec, self.vd = clearance, width, hole_clear, edge_clear, via_d
        self.layers = ["F.Cu", "B.Cu"]
        self.items = []   # (layer or '*', net, kind, geom)
        self._collect()
        self.inside = self._board_mask()

    # ---------- geometry collection ----------
    def _collect(self):
        b = self.b
        for t in b.GetTracks():
            net = t.GetNetname()
            if t.GetClass() == "PCB_VIA":
                p = t.GetPosition()
                self.items.append(("*", net, "circle", (p.x / MM, p.y / MM, t.GetWidth(pcbnew.F_Cu) / MM / 2)))
                self.items.append(("*", net, "hole", (p.x / MM, p.y / MM, t.GetDrillValue() / MM / 2)))
            else:
                s, e = t.GetStart(), t.GetEnd()
                self.items.append((t.GetLayerName(), net, "seg",
                                   (s.x / MM, s.y / MM, e.x / MM, e.y / MM, t.GetWidth() / MM / 2)))
        for fp in b.GetFootprints():
            for pad in fp.Pads():
                net = pad.GetNetname()
                for L in self.layers:
                    lid = b.GetLayerID(L)
                    if not pad.IsOnLayer(lid):
                        continue
                    poly = pad.GetEffectivePolygon(lid, pcbnew.ERROR_INSIDE)
                    for oi in range(poly.OutlineCount()):
                        ch = poly.Outline(oi)
                        pts = [(ch.CPoint(i).x / MM, ch.CPoint(i).y / MM) for i in range(ch.PointCount())]
                        self.items.append((L, net, "poly", pts))
                if pad.HasHole():
                    p = pad.GetPosition()
                    d = pad.GetDrillSize()
                    self.items.append(("*", net, "hole", (p.x / MM, p.y / MM, max(d.x, d.y) / MM / 2)))

    def _board_mask(self):
        ps = pcbnew.SHAPE_POLY_SET()
        self.b.GetBoardPolygonOutlines(ps, False)
        ch = ps.Outline(0)
        pts = [(ch.CPoint(i).x / MM, ch.CPoint(i).y / MM) for i in range(ch.PointCount())]
        inside = self._pip(pts)
        d = self._dist_poly_edges(pts)
        return inside & (d >= self.ec)

    # ---------- raster helpers ----------
    def _pip(self, pts):
        X, Y = self.X, self.Y
        res = np.zeros(X.shape, bool)
        n = len(pts)
        for i in range(n):
            xa, ya = pts[i]; xb, yb = pts[(i + 1) % n]
            cond = ((ya > Y) != (yb > Y))
            with np.errstate(divide="ignore", invalid="ignore"):
                xint = xa + (Y - ya) * (xb - xa) / (yb - ya)
            res ^= cond & (X < xint)
        return res

    def _seg_dist(self, X, Y, xa, ya, xb, yb):
        dx, dy = xb - xa, yb - ya
        L2 = dx * dx + dy * dy
        if L2 == 0:
            return np.hypot(X - xa, Y - ya)
        t = np.clip(((X - xa) * dx + (Y - ya) * dy) / L2, 0, 1)
        return np.hypot(X - (xa + t * dx), Y - (ya + t * dy))

    def _dist_poly_edges(self, pts, X=None, Y=None):
        X = self.X if X is None else X; Y = self.Y if Y is None else Y
        d = np.full(X.shape, np.inf)
        n = len(pts)
        for i in range(n):
            xa, ya = pts[i]; xb, yb = pts[(i + 1) % n]
            d = np.minimum(d, self._seg_dist(X, Y, xa, ya, xb, yb))
        return d

    def _window(self, bx0, by0, bx1, by1):
        i0 = max(0, int((bx0 - self.x0) / self.res) - 1); i1 = min(self.nx, int((bx1 - self.x0) / self.res) + 2)
        j0 = max(0, int((by0 - self.y0) / self.res) - 1); j1 = min(self.ny, int((by1 - self.y0) / self.res) + 2)
        return j0, j1, i0, i1

    def _mark(self, grid, kind, g, infl, hole_infl):
        if kind == "circle":
            x, y, r = g; R = r + infl
            j0, j1, i0, i1 = self._window(x - R, y - R, x + R, y + R)
            if j0 >= j1 or i0 >= i1: return
            sub = np.hypot(self.X[j0:j1, i0:i1] - x, self.Y[j0:j1, i0:i1] - y) <= R
            grid[j0:j1, i0:i1] |= sub
        elif kind == "hole":
            x, y, r = g; R = r + hole_infl
            j0, j1, i0, i1 = self._window(x - R, y - R, x + R, y + R)
            if j0 >= j1 or i0 >= i1: return
            grid[j0:j1, i0:i1] |= np.hypot(self.X[j0:j1, i0:i1] - x, self.Y[j0:j1, i0:i1] - y) <= R
        elif kind == "seg":
            xa, ya, xb, yb, hw = g; R = hw + infl
            j0, j1, i0, i1 = self._window(min(xa, xb) - R, min(ya, yb) - R, max(xa, xb) + R, max(ya, yb) + R)
            if j0 >= j1 or i0 >= i1: return
            grid[j0:j1, i0:i1] |= self._seg_dist(self.X[j0:j1, i0:i1], self.Y[j0:j1, i0:i1], xa, ya, xb, yb) <= R
        elif kind == "poly":
            pts = g; xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
            j0, j1, i0, i1 = self._window(min(xs) - infl, min(ys) - infl, max(xs) + infl, max(ys) + infl)
            if j0 >= j1 or i0 >= i1: return
            Xs, Ys = self.X[j0:j1, i0:i1], self.Y[j0:j1, i0:i1]
            # inside test on sub-window
            ins = np.zeros(Xs.shape, bool); n = len(pts)
            for k in range(n):
                xa, ya = pts[k]; xb, yb = pts[(k + 1) % n]
                cond = ((ya > Ys) != (yb > Ys))
                with np.errstate(divide="ignore", invalid="ignore"):
                    xint = xa + (Ys - ya) * (xb - xa) / (yb - ya)
                ins ^= cond & (Xs < xint)
            grid[j0:j1, i0:i1] |= ins | (self._dist_poly_edges(pts, Xs, Ys) <= infl)

    def blocked(self, net, infl, hole_infl):
        """per-layer boolean grids of cells where a feature of half-size `infl`-clearance can't go"""
        out = {}
        for L in self.layers:
            g = ~self.inside.copy()
            for lay, n, kind, geom in self.items:
                if n == net and n != "":
                    continue
                if lay == "*" or lay == L:
                    self._mark(g, kind, geom, infl, hole_infl)
            out[L] = g
        return out

    # ---------- search ----------
    def cell(self, x, y):
        return int(round((y - self.y0) / self.res)), int(round((x - self.x0) / self.res))

    def route(self, net, start, goals, start_layers, goal_layers, via_cost=8.0, allow_via=True, avoid=None):
        tr = self.blocked(net, self.cl + self.w / 2 + 0.02, self.hc + self.w / 2 + 0.02)
        vb = self.blocked(net, self.cl + self.vd / 2 + 0.02, self.hc + self.vd / 2 + 0.02)
        if avoid:
            for L in self.layers:
                tr[L] |= avoid.get(L, False); vb[L] |= avoid.get(L, False)
        via_ok = ~(vb["F.Cu"] | vb["B.Cu"])
        Ls = self.layers
        sj, si = self.cell(*start)
        goal_set = set()
        for (gx, gy) in goals:
            gj, gi = self.cell(gx, gy)
            for L in goal_layers:
                goal_set.add((gj, gi, Ls.index(L)))
        def h(j, i):
            return min(math.hypot(j - gj, i - gi) for (gj, gi, _) in goal_set)
        pq = []; came = {}; cost = {}
        for L in start_layers:
            s = (sj, si, Ls.index(L)); cost[s] = 0; heapq.heappush(pq, (h(sj, si), 0, s)); came[s] = None
        steps = [(-1, 0, 1), (1, 0, 1), (0, -1, 1), (0, 1, 1), (-1, -1, 1.414), (-1, 1, 1.414), (1, -1, 1.414), (1, 1, 1.414)]
        found = None
        while pq:
            f, c, s = heapq.heappop(pq)
            if c > cost.get(s, 1e18): continue
            if s in goal_set: found = s; break
            j, i, l = s
            for dj, di, sc in steps:
                nj, ni = j + dj, i + di
                if not (0 <= nj < self.ny and 0 <= ni < self.nx): continue
                L = Ls[l]
                if tr[L][nj, ni] and (nj, ni, l) not in goal_set: continue
                # penalize direction changes lightly to get cleaner lines
                prev = came.get(s)
                turn = 0
                if prev and prev[2] == l:
                    pdj, pdi = j - prev[0], i - prev[1]
                    if (pdj, pdi) != (dj, di): turn = 0.6
                ns = (nj, ni, l); nc = c + sc + turn
                if nc < cost.get(ns, 1e18):
                    cost[ns] = nc; came[ns] = s; heapq.heappush(pq, (nc + h(nj, ni), nc, ns))
            if allow_via and via_ok[j, i]:
                ns = (j, i, 1 - l); nc = c + via_cost
                if nc < cost.get(ns, 1e18) and not tr[Ls[1 - l]][j, i]:
                    cost[ns] = nc; came[ns] = s; heapq.heappush(pq, (nc + h(j, i), nc, ns))
        if not found:
            return None
        path = []; s = found
        while s is not None: path.append(s); s = came[s]
        return path[::-1]

    def to_mm(self, j, i):
        return self.x0 + i * self.res, self.y0 + j * self.res

    def simplify(self, path):
        """-> list of ('seg', layer, (x1,y1),(x2,y2)) and ('via', (x,y))"""
        out = []; Ls = self.layers
        k = 0
        while k < len(path) - 1:
            j, i, l = path[k]
            if path[k + 1][2] != l:
                out.append(("via", self.to_mm(j, i))); k += 1; continue
            # extend straight run
            dj, di = path[k + 1][0] - j, path[k + 1][1] - i
            m = k + 1
            while m + 1 < len(path) and path[m + 1][2] == l and (path[m + 1][0] - path[m][0], path[m + 1][1] - path[m][1]) == (dj, di):
                m += 1
            out.append(("seg", Ls[l], self.to_mm(j, i), self.to_mm(path[m][0], path[m][1])))
            k = m
        return out

def add_route(board, net_name, parts, width=0.25, via_d=0.8, via_drill=0.4):
    net = board.FindNet(net_name)
    for p in parts:
        if p[0] == "via":
            v = pcbnew.PCB_VIA(board); v.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(p[1][0]), pcbnew.FromMM(p[1][1])))
            v.SetWidth(pcbnew.FromMM(via_d)); v.SetDrill(pcbnew.FromMM(via_drill)); v.SetNet(net)
            v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); board.Add(v)
        else:
            _, L, a, c = p
            t = pcbnew.PCB_TRACK(board)
            t.SetStart(pcbnew.VECTOR2I(pcbnew.FromMM(a[0]), pcbnew.FromMM(a[1])))
            t.SetEnd(pcbnew.VECTOR2I(pcbnew.FromMM(c[0]), pcbnew.FromMM(c[1])))
            t.SetWidth(pcbnew.FromMM(width)); t.SetLayer(board.GetLayerID(L)); t.SetNet(net); board.Add(t)

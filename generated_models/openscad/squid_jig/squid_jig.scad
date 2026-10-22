// ===== Squid Jig Body =====
// A spindle-shaped squid jig body that slides on a line or wire. The fat end (tail) has a
// socket for the hub of a squid-jig crown (the ring of barbless needles); the line runs
// through a centre bore and exits at the rounded nose.
// Reverse-engineered from squid_jig_v1.3mf: 40 mm long, Ø10.6 mm at the belly.
// Prints standing on its tail, no supports (the original was printed in PLA at 100 % infill).

/* [Body] */
length       = 40;    // overall length, tail to nose
belly_d      = 10.6;  // largest diameter
belly_pos    = 10;    // distance of the widest point from the tail
nose_d       = 5;     // diameter where the nose would end before rounding
end_round    = 2;     // rounding radius of the tail and nose edges

/* [Line bore and crown socket] */
bore_d       = 2;     // centre hole for the line / leader wire
socket_d     = 5;     // socket in the tail for the crown hub
socket_depth = 8;     // depth of that socket

/* [Print layout] */
copies       = 1;     // how many bodies to lay out (the original plate had 12)
spacing      = 25;    // centre distance between bodies on the plate

$fa = 5; $fs = 0.25;

// ---- body curve: one circular arc in the (z, r) plane, flat (widest) at belly_pos ----
// The arc passes through (belly_pos, belly_r) with a horizontal tangent and through
// (length, nose_r); the tail diameter follows from that (≈ Ø10 for the defaults).
belly_r = belly_d / 2;
nose_r  = nose_d / 2;
arc_R   = (pow(length - belly_pos, 2) + pow(belly_r - nose_r, 2)) / (2 * (belly_r - nose_r));
function body_r(z) = belly_r - arc_R + sqrt(arc_R * arc_R - pow(z - belly_pos, 2));
tail_r  = body_r(0);

steps = 120;

// Full silhouette (both sides of the axis) so the end edges can be rounded in 2D.
module silhouette() {
    right = [for (i = [0:steps]) let(z = length * i / steps) [body_r(z), z]];
    left  = [for (i = [steps:-1:0]) let(z = length * i / steps) [-body_r(z), z]];
    polygon(concat(right, left));
}

module body_profile() {   // right half of the rounded silhouette, for rotate_extrude
    intersection() {
        offset(r = end_round) offset(delta = -end_round) silhouette();
        translate([0, -1]) square([belly_r + 1, length + 2]);
    }
}

module squid_jig_body() {
    difference() {
        rotate_extrude() body_profile();
        // line bore, straight through
        translate([0, 0, -1]) cylinder(d = bore_d, h = length + 2, $fn = 30);
        // crown socket in the tail
        translate([0, 0, -1]) cylinder(d = socket_d, h = socket_depth + 1);
    }
}

// Lay the bodies out on a grid, standing on their tails.
cols = ceil(sqrt(copies));
for (i = [0 : copies - 1])
    translate([(i % cols) * spacing, floor(i / cols) * spacing, 0]) squid_jig_body();

echo(str("Tail diameter: ", 2 * tail_r, " mm, arc radius: ", arc_R, " mm"));

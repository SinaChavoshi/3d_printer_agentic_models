// ===== Four-Colour Race Car Kit =====
// A push-together toy race car printed in four colours, no glue needed for the inlays:
//   BLUE body | WHITE side stripes + roof number | BLACK wheels + windshield | ORANGE headlamps
// Wheels spin on two 4 mm metal (or wooden dowel) axle rods, each about 44 mm long, through the body.
// Print each colour as its own plate with print_part = 1..4, or everything at once with 0.

/* [View] */
show_assembled = false;   // true = coloured assembled preview, false = print layout
print_part     = 0;       // 0 = all parts, 1 = body (blue), 2 = black parts, 3 = white parts, 4 = orange parts

/* [Body] */
car_len       = 100;   // overall body length
car_w         = 46;    // overall body width
deck_h        = 23;    // height of hood/rear deck (body coords)
hood_front_h  = 20;    // height of hood near the nose
roof_h        = 34;    // roof height (body coords)
cabin_inset   = 5;     // cabin inset from body sides at its base
ws_x0         = 34;    // windshield base X
roof_x0       = 52;    // roof start X
rw_x          = 72;    // roof end / rear window top X
cab_x1        = 88;    // rear window base X
spoiler_h     = 5;     // spoiler post height above deck
edge_r        = 2.5;   // radius of rounded body edges

/* [Wheels & axle] */
ground_clr    = 2;     // body underside clearance
wheel_r       = 10;    // wheel radius
wheel_w       = 9;     // wheel width
wheel_x_front = 20;    // front axle X
wheel_x_rear  = 80;    // rear axle X
axle_d        = 4;     // axle rod diameter
wheel_hole_clr = 0.1;  // extra clearance in the wheel hole (snug fit on the rod)
hub_r         = 6;     // hub recess radius
wheel_round   = 1.5;   // rounding radius of wheel edges

/* [Inlays & fit] */
fit_clr       = 0.2;   // clearance for axle holes / windshield insert
inlay_clr     = 0.15;  // per-side clearance for inlay pieces
inlay_depth   = 1.2;   // depth of stripe / number pockets and pieces
shield_depth  = 1.6;   // windshield insert thickness
ws_s0         = 3;     // insert start along windshield slope
ws_len        = 16;    // insert length along slope
ws_w          = 24;    // insert width
stripe_x      = 34;    // side stripe start X
stripe_z      = 5;     // side stripe base Z
race_number   = "27";  // number on the roof
num_size      = 10;    // roof number text size
num_x         = 62;    // roof number centre X

/* [Headlamps] */
lamp_d        = 8;     // headlamp diameter
lamp_depth    = 2.5;   // depth of lamp pocket / plug
lamp_dome     = 2.2;   // how far the dome sticks out of the nose
lamp_y        = 11;    // lamp offset from centreline
lamp_z        = 7.5;   // lamp centre height (body coords)

$fa = 2; $fs = 0.4;

// ---- derived ----
wheel_zb  = wheel_r - ground_clr;          // axle height in body coords
arch_r    = wheel_r + 1;                   // wheel arch radius
arch_top  = 11.5;                          // arch flat-top height above axle
ws_ang    = atan2(roof_h - (deck_h - 1), roof_x0 - ws_x0);
ins_len   = ws_len - 2*fit_clr;
ins_w     = ws_w - 2*fit_clr;
stripe_len = 34;
stripe_h   = 13;

// ================= helpers =================
module ball(r) {   // sphere with true poles so it sits exactly on z extents
    rotate_extrude($fn=16)
        polygon([for (a=[-90:15:90]) [r*cos(a), r*sin(a)]]);
}

// ================= 2D shapes =================
module lower_profile() {
    polygon([[2,0],[car_len-2,0],[car_len,3],[car_len,deck_h-3],
             [car_len-4,deck_h],[36,deck_h],[8,hood_front_h],
             [1,15],[0,11],[0,3]]);
}
module cabin_profile() {
    polygon([[ws_x0,deck_h-1],[cab_x1,deck_h-1],[rw_x,roof_h],[roof_x0,roof_h]]);
}
module top_shape() {
    hull() for (s=[-1,1]) {
        translate([8, s*(car_w/2-8)]) circle(8);
        translate([car_len-4, s*(car_w/2-4)]) circle(4);
    }
}
module arch2d() {   // truncated teardrop: printable arch roof
    intersection() {
        hull() {
            circle(arch_r);
            polygon([[-arch_r/sqrt(2), arch_r/sqrt(2)],
                     [ arch_r/sqrt(2), arch_r/sqrt(2)],
                     [0, arch_r*sqrt(2)]]);
        }
        translate([-arch_r-1, -arch_r-wheel_zb-1])
            square([2*arch_r+2, arch_r+wheel_zb+1+arch_top]);
    }
}
module stripe2d() {   // slanted speed stripe that rises toward the rear
    polygon([[0,2],[29,7],[stripe_len,stripe_h],[5,8]]);
}
module number2d() {
    rotate(-90) text(race_number, size=num_size, font="DejaVu Sans:style=Bold",
                    halign="center", valign="center");
}

// ================= Body (BLUE) =================
module lower_body() {   // eroded core + sphere = all edges rounded
    minkowski() {
        intersection() {
            rotate([90,0,0]) translate([0,0,-(car_w/2-edge_r)])
                linear_extrude(car_w-2*edge_r) offset(delta=-edge_r) lower_profile();
            translate([0,0,-1]) linear_extrude(deck_h+2) offset(r=-edge_r) top_shape();
        }
        ball(edge_r);
    }
}
module cabin() {
    minkowski() {
        intersection() {
            rotate([90,0,0]) translate([0,0,-(car_w/2-edge_r)])
                linear_extrude(car_w-2*edge_r) offset(delta=-edge_r) cabin_profile();
            hull() {
                translate([0, -(car_w/2-cabin_inset-edge_r), deck_h-1+edge_r])
                    cube([car_len, car_w-2*cabin_inset-2*edge_r, 0.01]);
                translate([0, -(car_w/2-cabin_inset-4-edge_r), roof_h-edge_r-0.01])
                    cube([car_len, car_w-2*cabin_inset-8-2*edge_r, 0.01]);
            }
        }
        ball(edge_r);
    }
}
module spoiler() {
    for (s=[-1,1])
        translate([90, s*11-1.5, deck_h-0.5]) cube([6, 3, spoiler_h+0.51]);
    // rounded wing, 2 mm thick
    hull() for (x=[89.5, 98], y=[-16, 16])
        translate([x, y, deck_h+spoiler_h+1]) ball(1);
}
module shield_frame() {
    translate([ws_x0, 0, deck_h-1]) rotate([0,-ws_ang,0]) children();
}
module side_stripe_pocket() {
    translate([stripe_x, car_w/2+1, stripe_z]) rotate([90,0,0])
        linear_extrude(inlay_depth+1) stripe2d();
}
module body() {
    difference() {
        union() { lower_body(); cabin(); spoiler(); }
        // wheel arches
        for (x=[wheel_x_front, wheel_x_rear], m=[0,1]) mirror([0,m,0])
            translate([x, car_w/2+1, wheel_zb]) rotate([90,0,0])
                linear_extrude(wheel_w+3) arch2d();
        // through holes for the axle rods
        for (x=[wheel_x_front, wheel_x_rear])
            translate([x, -car_w/2-1, wheel_zb]) rotate([-90,0,0])
                cylinder(d=axle_d+fit_clr, h=car_w+2);
        // side stripe pockets, both sides
        side_stripe_pocket();
        mirror([0,1,0]) side_stripe_pocket();
        // windshield insert pocket
        shield_frame() translate([ws_s0, -ws_w/2, -shield_depth])
            cube([ws_len, ws_w, shield_depth+2]);
        // roof number pocket
        translate([num_x, 0, roof_h-inlay_depth]) linear_extrude(inlay_depth+1) number2d();
        // headlamp pockets in the nose
        for (s=[-1,1])
            translate([-1, s*lamp_y, lamp_z]) rotate([0,90,0])
                cylinder(d=lamp_d+2*inlay_clr, h=lamp_depth+1);
    }
}

// ================= Wheels (BLACK) =================
module wheel() {   // outer face at z=0, axle hole through along Z, rounded edges
    difference() {
        rotate_extrude()
            offset(r=wheel_round) offset(delta=-wheel_round)
                square([wheel_r, wheel_w]);
        translate([0,0,-1]) cylinder(d=axle_d+wheel_hole_clr, h=wheel_w+2);
        translate([0,0,-0.01]) cylinder(r1=hub_r, r2=hub_r-1.2, h=1.2);
    }
}

// ================= Windshield (BLACK) =================
module shield_insert() { cube([ins_len, ins_w, shield_depth]); }   // tinted glass panel

// ================= Headlamp (ORANGE) =================
module headlamp() {   // z=0 is the back of the plug, dome points up (+z)
    cylinder(d=lamp_d-2*inlay_clr, h=lamp_depth+0.01);
    translate([0,0,lamp_depth])
        intersection() {
            scale([1,1,lamp_dome/((lamp_d-2*inlay_clr)/2)])
                sphere(d=lamp_d-2*inlay_clr, $fn=40);
            translate([-lamp_d, -lamp_d, 0]) cube([2*lamp_d, 2*lamp_d, lamp_dome+1]);
        }
}

// ================= Inlays (WHITE) =================
module stripe_piece() { linear_extrude(inlay_depth) offset(delta=-inlay_clr) stripe2d(); }
module number_piece() { linear_extrude(inlay_depth) offset(delta=-inlay_clr) number2d(); }

// ================= Assembly / layout =================
module assembled() {
    translate([0,0,ground_clr]) {
        color("royalblue") body();
        color("white") {
            translate([stripe_x, car_w/2, stripe_z]) rotate([90,0,0]) stripe_piece();
            mirror([0,1,0]) translate([stripe_x, car_w/2, stripe_z]) rotate([90,0,0]) stripe_piece();
            translate([num_x, 0, roof_h-inlay_depth]) number_piece();
        }
        color("black") shield_frame() translate([ws_s0+fit_clr, -ws_w/2+fit_clr, -shield_depth]) shield_insert();
        color("orange") for (s=[-1,1])
            translate([lamp_depth, s*lamp_y, lamp_z]) rotate([0,-90,0]) headlamp();
    }
    color("black") for (x=[wheel_x_front, wheel_x_rear]) {
        translate([x,  car_w/2-1, wheel_r]) rotate([90,0,0])  wheel();
        translate([x, -car_w/2+1, wheel_r]) rotate([-90,0,0]) wheel();
    }
}

module print_layout() {
    show = function(p) print_part == 0 || print_part == p;
    if (show(1)) color("royalblue") body();
    // row 2: wheels and windshield (black)
    row2 = car_w/2 + 10 + wheel_r;
    if (show(2)) color("black") {
        for (i=[0:3]) translate([wheel_r + i*(2*wheel_r+10), row2, 0]) wheel();
        translate([4*(2*wheel_r+10), row2 - ins_w/2, 0]) shield_insert();
    }
    // row 3: stripes and number (white), headlamps (orange)
    row3 = row2 + wheel_r + 10;
    if (show(3)) color("white") {
        translate([0, row3, 0]) stripe_piece();
        translate([stripe_len + 10 + stripe_len, row3, 0]) mirror([1,0,0]) stripe_piece();
        translate([2*stripe_len + 20 + num_size/2, row3 + num_size, 0]) rotate(90) number_piece();
    }
    if (show(4)) color("orange") for (i=[0:1])
        translate([2*stripe_len + 30 + 2*num_size + lamp_d/2 + i*(lamp_d+8), row3 + lamp_d/2, 0]) headlamp();
}

if (show_assembled) assembled(); else print_layout();

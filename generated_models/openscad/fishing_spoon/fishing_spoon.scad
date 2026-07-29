// 3.5" Puget Sound Coho Lure - Kite/Buzz Bomb Profile (Artifact-Free)
// Features: Angular Taper, Compound Arch/Twist, Deep-Sunk Tube, V-Groove Scales, Flush Eye

$fn = 60; // Base curve resolution

// --- Toggles & Parameters ---
twist_angle = 60;       
enable_scales = false;  
eye_diameter = 9.0;     
eye_depth = 1.0;        
tunnel_sink = 1.5;      
render_steps = 50;      // Increased for smoother curves

length = 88.9;          
max_width = 17.0;       
blade_thickness = 2.2;  
cup_radius = 180.0;     

tunnel_outer = 5.5;
tunnel_inner = 2.4;
fillet_width = 12.0;    

// 1. Math Functions for Angular Kite Taper
function clamp(v, min_v, max_v) = (v < min_v) ? min_v : ((v > max_v) ? max_v : v);

function get_width(z) = 
    let (
        widest_z = -length/5, // Shoulder aligns with eye socket
        nose_w = 6.0,         // Minimum width to encapsulate the tunnel
        tail_w = 8.0,
        cz = clamp(z, -length/2, length/2)
    )
    (cz < widest_z) ? 
        // Linear taper from nose to shoulder
        nose_w + (max_width - nose_w) * ((cz - (-length/2)) / (widest_z - (-length/2))) : 
        // Linear taper from shoulder to tail
        max_width - (max_width - tail_w) * ((cz - widest_z) / ((length/2) - widest_z));

// 2. 2D Cupped Cross Section
module cross_section(w, shrink=0) {
    bt_outer = blade_thickness - shrink;
    to = tunnel_outer - shrink;
    
    if (bt_outer > 0 && to > 0) {
        union() {
            intersection() {
                translate([0, -cup_radius + blade_thickness]) 
                difference() {
                    circle(r=cup_radius - shrink);
                    circle(r=cup_radius - blade_thickness);
                }
                translate([-w/2, -cup_radius]) square([w, cup_radius*2]);
            }
            hull() {
                translate([0, -tunnel_outer/2 + tunnel_sink]) circle(d=to);
                translate([-min(w, fillet_width)/2, 0]) square([min(w, fillet_width), 0.1]);
            }
        }
    }
}

// 3. Compound 3D Helical/Arched Body Generator (Fixed Lofting)
module twisted_arched_body(shrink=0) {
    step_size = length / render_steps;
    overlap = 0.05; // Fixes coplanar "cut" artifacts by welding slices together
    
    for (i = [0 : render_steps - 1]) {
        z1 = -length/2 + i * step_size;
        z2 = z1 + step_size + overlap; 
        
        w1 = get_width(z1);
        w2 = get_width(z2);
        
        a1 = (z1 / length) * twist_angle;
        a2 = (z2 / length) * twist_angle;
        
        theta1 = asin(z1 / cup_radius);
        y1 = cup_radius * cos(theta1) - cup_radius;
        
        theta2 = asin(clamp(z2, -cup_radius, cup_radius) / cup_radius);
        y2 = cup_radius * cos(theta2) - cup_radius;
        
        hull() {
            translate([0, y1, z1]) 
            rotate([theta1, 0, 0]) 
            rotate([0, 0, a1])     
                linear_extrude(height=0.01, center=true) cross_section(w1, shrink);
                
            translate([0, y2, z2]) 
            rotate([theta2, 0, 0]) 
            rotate([0, 0, a2]) 
                linear_extrude(height=0.01, center=true) cross_section(w2, shrink);
        }
    }
}

// 4. Compound Arched & Sunk Internal Line Conduit
module twisted_arched_tunnel() {
    step_size = length / render_steps;
    overlap = 0.05;
    
    for (i = [-1 : render_steps]) {
        z1 = -length/2 + i * step_size;
        z2 = z1 + step_size + overlap;
        
        a1 = (z1 / length) * twist_angle;
        a2 = (z2 / length) * twist_angle;
        
        theta1 = asin(clamp(z1, -cup_radius, cup_radius) / cup_radius);
        y1 = cup_radius * cos(theta1) - cup_radius;
        
        theta2 = asin(clamp(z2, -cup_radius, cup_radius) / cup_radius);
        y2 = cup_radius * cos(theta2) - cup_radius;
        
        hull() {
            translate([0, y1, z1]) 
            rotate([theta1, 0, 0]) 
            rotate([0, 0, a1]) 
                translate([0, -tunnel_outer/2 + tunnel_sink]) cylinder(d=tunnel_inner, h=0.01, $fn=20);
                
            translate([0, y2, z2]) 
            rotate([theta2, 0, 0]) 
            rotate([0, 0, a2]) 
                translate([0, -tunnel_outer/2 + tunnel_sink]) cylinder(d=tunnel_inner, h=0.01, $fn=20);
        }
    }
}

// 5. Diagonal Scale Texture Matrix
module scale_texture() {
    spacing = 3.5; 
    for (i = [-length*1.5 : spacing : length*1.5]) {
        translate([0, 0, i]) rotate([0, 45, 0]) cube([max_width*2, max_width*2, 0.6], center=true);
        translate([0, 0, i]) rotate([0, -45, 0]) cube([max_width*2, max_width*2, 0.6], center=true);
    }
}

// 6. Dynamic Eye Socket 
module eye_socket() {
    eye_z = -length/5;
    
    theta = asin(eye_z / cup_radius);
    eye_y = cup_radius * cos(theta) - cup_radius;
    a = (eye_z / length) * twist_angle;
    
    translate([0, eye_y, eye_z])
    rotate([theta, 0, 0])
    rotate([0, 0, a])
    translate([0, blade_thickness - eye_depth, 0])
    rotate([-90, 0, 0]) 
    cylinder(d=eye_diameter, h=20, $fn=40); // Height increased to ensure clean outward cut
}

// Final Assembly
difference() {
    if (enable_scales) {
        union() {
            twisted_arched_body(0.4); 
            difference() {
                twisted_arched_body(0); 
                scale_texture();        
            }
        }
    } else {
        twisted_arched_body(0.4); 
    }
    
    twisted_arched_tunnel();
    eye_socket();
    
    // Cleanly trims off any excess length created by the new overlap algorithm
    translate([0, 0, length/2 + 4.9]) cube([max_width*2, max_width*2, 10], center=true);
    translate([0, 0, -length/2 - 4.9]) cube([max_width*2, max_width*2, 10], center=true);
}
// Trapezoidal Cradle Bracket with Extended Tape Base (Sides and Bottom)
// Fits WOLFBOX G840S: Front 40mm, Back 50mm, Depth 35mm, Height 32mm

cam_front = 40;     
cam_back = 50;      
cam_depth = 35;     
cam_height = 32;    
wall = 3;           
clearance = 1;      

// Adjustable Tape Base Parameters
tape_wing_width = 25;      // Extra width on EACH side (mm)
tape_lower_extension = 20; // Extra surface area BELOW the base plate for tape (mm)

f_w = cam_front + (clearance * 2); 
b_w = cam_back + (clearance * 2);  
plate_w = b_w + (tape_wing_width * 2); 
plate_h = cam_height + wall + tape_lower_extension;

module rigid_camera_mount() {
    difference() {
        union() {
            // Front Adhesive Plate (against glass, extends downwards)
            translate([0, wall/2, (cam_height + wall - tape_lower_extension)/2])
                cube([plate_w, wall, plate_h], center=true);
            
            // Horizontal Base Plate (camera floor)
            linear_extrude(height = wall)
            polygon([
                [-(f_w/2 + wall), 0],
                [ (f_w/2 + wall), 0],
                [ (b_w/2 + wall), cam_depth],
                [-(b_w/2 + wall), cam_depth]
            ]);
            
            // Left Triangular Gusset
            hull() {
                translate([-(f_w/2 + wall), 0, 0])
                    cube([wall, wall, cam_height + wall]);
                translate([-(b_w/2 + wall), cam_depth - wall, 0])
                    cube([wall, wall, wall]);
            }
            
            // Right Triangular Gusset
            hull() {
                translate([(f_w/2), 0, 0])
                    cube([wall, wall, cam_height + wall]);
                translate([(b_w/2), cam_depth - wall, 0])
                    cube([wall, wall, wall]);
            }
        }
        
        // Rectangular Cutout for Camera Head
        translate([0, wall/2, (cam_height/2) + wall])
            cube([f_w, wall + 2, cam_height], center=true);
    }
}

rigid_camera_mount();
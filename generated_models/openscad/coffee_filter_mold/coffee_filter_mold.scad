// --- Parameters ---

// Dimensions of your Stainless Steel Pod (Inner Dimensions)
pod_top_diameter = 42;    // Top opening diameter of your pod (standard K-cup ~50-51mm)
pod_bottom_diameter = 35; // Bottom diameter of your pod (standard K-cup ~33-37mm)
pod_depth = 32;           // Depth of the pod

// Flute (Star Pattern) Configuration
num_flutes = 12;          // Number of "star" points/pleats (12-16 is usually good for filters) 
flute_depth = 1.5;        // How deep the ridges are (amplitude of the wave)

// Tolerances & Material
paper_thickness = 0.3;    // Approx thickness of coffee filter paper
fit_tolerance = 0.4;      // Extra gap for 3D print clearance (increase if prints fit too tight)

// Mold Structural Settings
mold_wall = 3;            // Thickness of the mold walls
base_height = 5;          // Thickness of the receiver base plate
handle_height = 15;       // Height of the handle on the ram

// Smoothness of the curves (higher = smoother but slower render)
$fn = 100;

// --- Calculated Values ---
// Calculate radii
top_r = pod_top_diameter / 2;
bot_r = pod_bottom_diameter / 2;

// The gap needs to account for paper + clearance
total_gap = paper_thickness + fit_tolerance;


// --- Main Render Logic ---
// Un-comment the part you want to see/export

translate([-35, 0, 0]) receiver();
translate([35, 0, 0])  ram();

// --- Modules ---

module ram() {
    color("CornflowerBlue") 
    union() {
        // The pressing form (Male)
        // We subtract the gap from the dimensions to make it fit inside
        make_shape(
            h = pod_depth, 
            r_top = top_r - total_gap, 
            r_bot = bot_r - total_gap, 
            flutes = num_flutes, 
            amp = flute_depth
        );
        
        // Handle
        translate([0, 0, pod_depth])
        cylinder(h=handle_height, r1=10, r2=12);
        
        // Handle Top Cap (rounding)
        translate([0, 0, pod_depth + handle_height])
        sphere(r=12);
    }
}

module receiver() {
    color("LightSalmon") 
    difference() {
        // Exterior solid block/cup
        union() {
            cylinder(h = pod_depth + base_height, r = top_r + mold_wall);
            
            // Wider base for stability
            cylinder(h = base_height, r = top_r + mold_wall + 5);
        }

        // Interior cutout (Female)
        // We lift it up by base_height so it has a floor
        translate([0, 0, base_height])
        make_shape(
            h = pod_depth + 1, // +1 to ensure it cuts through top
            r_top = top_r, 
            r_bot = bot_r, 
            flutes = num_flutes, 
            amp = flute_depth + 0.2 // Slightly deeper flutes on receiver to prevent binding at tips
        );
    }
}

// --- Geometry Helper Module ---
// Creates a lofted star/fluted cylinder
module make_shape(h, r_top, r_bot, flutes, amp) {
    linear_extrude(height = h, twist = 0, scale = r_top / r_bot, slices = 50) {
        star_profile(r = r_bot, flutes = flutes, amp = amp);
    }
}

// Creates the 2D star profile
module star_profile(r, flutes, amp) {
    // Generate points for the star shape
    points = [
        for (i = [0 : 360]) 
            let (angle = i)
            let (radius_offset = amp * cos(flutes * angle))
            [ (r + radius_offset) * cos(angle), (r + radius_offset) * sin(angle) ]
    ];
    polygon(points);
}

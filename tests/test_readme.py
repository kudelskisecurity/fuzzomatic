from fuzzomatic.tools import llm


def test_extract_fuzz_target_contains_snippet():
    response = """
To use the library's principal function and write a fuzz target in Rust using the xml-rs library, you can follow the example below:                                                                                                                                            
                                                                                                                                                                                                                                                                               
```                                                                                                                                                                                                                                                                            
#![no_main]                                                                                                                                                                                                                                                                    
                                                                                                                                                                                                                                                                               
use libfuzzer_sys::fuzz_target;                                                                                                                                                                                                                                                
use xml::reader::{EventReader, XmlEvent}; // Include necessary dependencies                                                                                                                                                                                                    
                                                                                                                                                                                                                                                                               
fuzz_target!(|data: &[u8]| {                                                                                                                                                                                                                                                   
    // Parse the XML document                                                                                                                                                                                                                                                  
    let parser = EventReader::from_reader(data);                                                                                                                                                                                                                               
    let mut depth = 0;                                                                                                                                                                                                                                                         
                                                                                                                                                                                                                                                                               
    // Iterate over the XML events                                                                                                                                                                                                                                             
    for event in parser {                                                                                                                                                                                                                                                      
        match event {                                                                                                                                                                                                                                                          
            Ok(XmlEvent::StartElement { name, .. }) => {                                                                                                                                                                                                                       
                depth += 1;                                                                                                                                                                                                                                                    
            }                                                                                                                                                                                                                                                                  
            Ok(XmlEvent::EndElement { .. }) => {                                                                                                                                                                                                                               
                depth -= 1;                                                                                                                                                                                                                                                    
            }                                                                                                                                                                                                                                                                  
            Ok(XmlEvent::Characters(_)) => {                                                                                                                                                                                                                                   
                // Fuzzed code goes here                                                                                                                                                                                                                                       
                // ...                                                                                                                                                                                                                                                         
            }                                                                                                                                                                                                                                                                  
            Err(_) => {                                                                                                                                                                                                                                                        
                // Handle parsing errors, if necessary
                // ...
            }
            _ => {}
        }
    }
});
```

In this example, we import the necessary dependencies from the xml-rs library using the `use` statement. Then, within the fuzz target function, we create an `EventReader` from the input `data` and iterate over the XML events. We handle the start and end element events by incrementing and decrementing the `depth` variable, and for character events, we can insert the fuzzed code that we want to test.
"""
    snippet = llm.extract_fuzz_target(response, "")
    assert snippet is not None


def test_extract_fuzz_target_multiple_code_blocks():
    response = """
To use the library's principal function and write a fuzz target in Rust using the xml-rs library, you can follow the example below:                                                                                                                                            

```                                                                                                                                                                                                                                                                            
#![no_main]                                                                                                                                                                                                                                                                    

use libfuzzer_sys::fuzz_target;                                                                                                                                                                                                                                                
use xml::reader::{EventReader, XmlEvent}; // Include necessary dependencies                                                                                                                                                                                                    

fuzz_target!(|data: &[u8]| {                                                                                                                                                                                                                                                   
    // Parse the XML document                                                                                                                                                                                                                                                  
    let parser = EventReader::from_reader(data);                                                                                                                                                                                                                               
    let mut depth = 0;                                                                                                                                                                                                                                                         

    // Iterate over the XML events                                                                                                                                                                                                                                             
    for event in parser {                                                                                                                                                                                                                                                      
        match event {                                                                                                                                                                                                                                                          
            Ok(XmlEvent::StartElement { name, .. }) => {                                                                                                                                                                                                                       
                depth += 1;                                                                                                                                                                                                                                                    
            }                                                                                                                                                                                                                                                                  
            Ok(XmlEvent::EndElement { .. }) => {                                                                                                                                                                                                                               
                depth -= 1;                                                                                                                                                                                                                                                    
            }                                                                                                                                                                                                                                                                  
            Ok(XmlEvent::Characters(_)) => {                                                                                                                                                                                                                                   
                // Fuzzed code goes here                                                                                                                                                                                                                                       
                // ...                                                                                                                                                                                                                                                         
            }                                                                                                                                                                                                                                                                  
            Err(_) => {                                                                                                                                                                                                                                                        
                // Handle parsing errors, if necessary
                // ...
            }
            _ => {}
        }
    }
});
```

In this example, we import the necessary dependencies from the xml-rs library using the `use` statement. Then, within the fuzz target function, we create an `EventReader` from the input `data` and iterate over the XML events. We handle the start and end element events by incrementing and decrementing the `depth` variable, and for character events, we can insert the fuzzed code that we want to test.

To run the fuzz target, run the following command:

```
cargo fuzz run fuzz_target_1
```
"""
    snippet = llm.extract_fuzz_target(response, "")
    assert snippet is not None


def test_extract_fuzz_target_no_snippet():
    response = """
Something that doesn't contain any code blocks or anything useful.
"""
    snippet = llm.extract_fuzz_target(response, "")
    assert snippet is None


def test_fuzz_target_is_useful():
    response = """To use the principal function of the xml-rs library, you would need to:                                                                                                                                                                                                        
                                                                                                                                                                                                                                                                               
1. Add the library as a dependency in your `Cargo.toml` file:                                                                                                                                                                                                                  
   ```toml                                                                                                                                                                                                                                                                     
   [dependencies]                                                                                                                                                                                                                                                              
   xml-rs = "0.8.16"                                                                                                                                                                                                                                                           
   ```                                                                                                                                                                                                                                                                         
                                                                                                                                                                                                                                                                               
2. Import the necessary modules in your fuzz target code:                                                                                                                                                                                                                      
   ```rust                                                                                                                                                                                                                                                                     
   #![no_main]                                                                                                                                                                                                                                                                 
                                                                                                                                                                                                                                                                               
   use libfuzzer_sys::fuzz_target;                                                                                                                                                                                                                                             
   use xml::reader::{EventReader, XmlEvent};                                                                                                                                                                                                                                   
   use std::io::Cursor;                                                                                                                                                                                                                                                        
                                                                                                                                                                                                                                                                               
   fuzz_target!(|data: &[u8]| {                                                                                                                                                                                                                                                
       let cursor = Cursor::new(data);                                                                                                                                                                                                                                         
       let parser = EventReader::new(cursor);                                                                                                                                                                                                                                  
                                                                                                                                                                                                                                                                               
       // principal function code goes here                                                                                                                                                                                                                                    
   });                                                                                                                                                                                                                                                                         
   ```                                                                                                                                                                                                                                                                         
                                                                                                                
3. Use the principal function of the xml-rs library to process the XML events:                                                                                                                                                                                                 
   ```rust                                                                                                                                                                                                                                                                     
   #![no_main]                                                                                                                                                                                                                                                                 
                                                                                                                                                                                                                                                                               
   use libfuzzer_sys::fuzz_target;                                                                                                                                                                                                                                             
   use xml::reader::{EventReader, XmlEvent};                                                                                                                                                                                                                                   
   use std::io::Cursor;                                                                                                                                                                                                                                                        
                                                                                                                                                                                                                                                                               
   fuzz_target!(|data: &[u8]| {                                                                                                                                                                                                                                                
       let cursor = Cursor::new(data);                                                                                                                                                                                                                                         
       let parser = EventReader::new(cursor);                                                                                                                                                                                                                                  
                                                                                                                                                                                                                                                                               
       let mut depth = 0;                                                                                                                                                                                                                                                      
       for e in parser {                                                                                                                                                                                                                                                       
           match e {                                                                                                                                                                                                                                                           
               Ok(XmlEvent::StartElement { name, .. }) => {                                                                                                                                                                                                                    
                   depth += 1;                                                                                                                                                                                                                                                 
               }
               Ok(XmlEvent::EndElement { name }) => {
                   depth -= 1;
               }
               Err(_) => {
                   break;
               }
               _ => {}
           }
       }
   });
   ```

This code uses the `EventReader` from the xml-rs library to parse XML events from the provided data. It then uses the principal function of the library to process the events and increment/decrement the `depth` variable based on the start and end elements. Note that this 
code example only includes the core logic of processing the events and does not include any output statements.
    
    """

    snippet = llm.extract_fuzz_target(response, "")

    assert "//" not in snippet

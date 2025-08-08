using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;


namespace KnowledgeClient
{
    class StreamResponse
    {
        public string response { get; set; }
        public string model { get; set; }
        public bool done { get; set; }
    }
}

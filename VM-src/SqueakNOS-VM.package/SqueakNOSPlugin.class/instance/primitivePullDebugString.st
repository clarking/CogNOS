debugging
primitivePullDebugString
	| dataOop dataPtr length console |

	self primitive: 'primitivePullDebugString'
		parameters: #().

	self var: #dataPtr type: 'unsigned char *'.
	self var: #console type: 'extern Console'.
	self var: #length type: 'unsigned long'.
	self cCode: 'length = strlen(console.text)'.
	dataOop := interpreterProxy instantiateClass: interpreterProxy classString indexableSize: length + 1.
	dataPtr := interpreterProxy firstIndexableField: dataOop.

	self cCode: 'strcpy(dataPtr, console.text)'. 
	self cCode: 'console_clear(&console)'.

	^ dataOop
